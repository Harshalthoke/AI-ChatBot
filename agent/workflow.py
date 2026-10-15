"""LangGraph agent workflow for research retrieval, verification, and journal ranking."""

import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END

from config.settings import settings
from models.research import ResearchProfile
from models.journal import JournalRecord, RepresentativePublication, JournalRankingResult
from models.evidence import VerificationStatus
from services.openalex_service import OpenAlexService
from services.crossref_service import CrossrefService
from services.doaj_service import DOAJService
from services.verification_service import VerificationService
from services.ranking_service import JournalRankingEngine
from services.llm_service import LLMService
from utils.deduplication import (
    get_canonical_journal_key,
    can_merge_journals,
    merge_journal_records,
    normalize_issn,
    canonical_title_slug
)
from utils.text_processing import generate_search_query_variations
from agent.state import ResearchAgentState

logger = logging.getLogger(__name__)


class JournalFinderWorkflow:
    """Manages the iterative search, deduplication, verification, and ranking loop."""

    def __init__(
        self,
        openalex_service: Optional[OpenAlexService] = None,
        crossref_service: Optional[CrossrefService] = None,
        verification_service: Optional[VerificationService] = None,
        ranking_engine: Optional[JournalRankingEngine] = None,
        llm_service: Optional[LLMService] = None
    ):
        self.openalex = openalex_service or OpenAlexService()
        self.crossref = crossref_service or CrossrefService()
        self.verification = verification_service or VerificationService()
        self.ranking = ranking_engine or JournalRankingEngine()
        self.llm = llm_service or LLMService()

    def generate_queries_node(self, state: ResearchAgentState) -> Dict[str, Any]:
        """Node 1: Generates initial targeted academic queries."""
        profile = state["profile"]
        queries = generate_search_query_variations(
            title=profile.title,
            keywords=profile.keywords,
            domain=profile.domain,
            key_concepts=profile.key_concepts
        )

        logs = list(state.get("status_logs", []))
        logs.append(f"Generated {len(queries)} targeted queries for scholarly discovery.")

        return {
            "queries": queries,
            "status_logs": logs
        }

    def search_venues_node(self, state: ResearchAgentState) -> Dict[str, Any]:
        """Node 2: Searches OpenAlex and Crossref for works and publication venues."""
        queries = state.get("queries", [])
        current_iter = state.get("current_iteration", 0) + 1
        api_calls = state.get("api_call_count", 0)
        logs = list(state.get("status_logs", []))

        # Select queries for this iteration
        query_idx = (current_iter - 1) % max(len(queries), 1)
        active_query = queries[query_idx] if queries else state["profile"].title

        logs.append(f"Iteration {current_iter}: Querying scholarly indices with: '{active_query[:60]}...'")

        # 1. OpenAlex Works search
        try:
            openalex_works = self.openalex.search_works(active_query, limit=12)
            api_calls += 1
        except Exception as e:
            logger.warning(f"OpenAlex works search failed: {e}")
            openalex_works = []

        # 2. OpenAlex Sources search
        try:
            openalex_sources = self.openalex.search_sources(active_query, limit=8)
            api_calls += 1
        except Exception as e:
            logger.warning(f"OpenAlex sources search failed: {e}")
            openalex_sources = []

        # 3. Crossref Works search
        try:
            crossref_works = self.crossref.search_works_by_query(active_query, limit=10)
            api_calls += 1
        except Exception as e:
            logger.warning(f"Crossref works search failed: {e}")
            crossref_works = []

        # Convert and merge into candidate dictionary
        existing_candidates = dict(state.get("candidate_journals", {}))
        initial_count = len(existing_candidates)

        # Process OpenAlex works
        for w in openalex_works:
            venue_name = w.get("venue_name")
            if not venue_name:
                continue

            issn_l = w.get("venue_issn_l")
            issns = w.get("venue_issns", [])
            p_issn = issns[0] if issns else None
            e_issn = issns[1] if len(issns) > 1 else None

            pub = RepresentativePublication(
                title=w.get("work_title", "Untitled"),
                doi=w.get("doi"),
                publication_year=w.get("publication_year"),
                cited_by_count=w.get("cited_by_count", 0),
                source_url=w.get("source_url")
            )

            record = JournalRecord(
                journal_id=issn_l or canonical_title_slug(venue_name),
                title=venue_name,
                issn_linking=issn_l,
                issn_print=p_issn,
                issn_electronic=e_e_issn if (e_e_issn := e_issn) else None,
                publisher=w.get("venue_publisher"),
                is_open_access=w.get("is_oa"),
                apc_usd=w.get("apc_usd"),
                representative_publications=[pub],
                source_urls=[w.get("source_url")] if w.get("source_url") else [],
                sources_contributed=["OpenAlex"]
            )
            self._upsert_journal(existing_candidates, record)

        # Process OpenAlex sources
        for s in openalex_sources:
            j_name = s.get("journal_name")
            if not j_name:
                continue

            issn_l = s.get("issn_l")
            issns = s.get("issns", [])
            p_issn = issns[0] if issns else None
            e_issn = issns[1] if len(issns) > 1 else None

            record = JournalRecord(
                journal_id=issn_l or canonical_title_slug(j_name),
                title=j_name,
                alternate_titles=s.get("alternate_titles", []),
                issn_linking=issn_l,
                issn_print=p_issn,
                issn_electronic=e_issn,
                publisher=s.get("publisher"),
                homepage_url=s.get("homepage_url"),
                subject_areas=s.get("subject_areas", []),
                is_open_access=s.get("is_oa"),
                apc_usd=s.get("apc_usd"),
                metrics=s.get("metrics", {}),
                source_urls=[s.get("source_url")] if s.get("source_url") else [],
                sources_contributed=["OpenAlex"]
            )
            self._upsert_journal(existing_candidates, record)

        # Process Crossref works
        for cw in crossref_works:
            v_name = cw.get("venue_name")
            if not v_name:
                continue

            issn_l = cw.get("venue_issn_l")
            pub = RepresentativePublication(
                title=cw.get("work_title", "Untitled"),
                doi=cw.get("doi"),
                publication_year=cw.get("publication_year"),
                source_url=cw.get("source_url")
            )

            record = JournalRecord(
                journal_id=issn_l or canonical_title_slug(v_name),
                title=v_name,
                issn_linking=issn_l,
                issn_print=cw.get("venue_issns", [None])[0],
                publisher=cw.get("venue_publisher"),
                representative_publications=[pub],
                source_urls=[cw.get("source_url")] if cw.get("source_url") else [],
                sources_contributed=["Crossref"]
            )
            self._upsert_journal(existing_candidates, record)

        new_count = len(existing_candidates)
        added_in_iter = new_count - initial_count
        no_progress = state.get("no_progress_count", 0)
        if added_in_iter == 0:
            no_progress += 1
        else:
            no_progress = 0

        logs.append(
            f"Found {added_in_iter} new journal candidate(s) (total candidates: {new_count})."
        )

        return {
            "candidate_journals": existing_candidates,
            "current_iteration": current_iter,
            "api_call_count": api_calls,
            "no_progress_count": no_progress,
            "status_logs": logs
        }

    def verify_evidence_node(self, state: ResearchAgentState) -> Dict[str, Any]:
        """Node 3: Verifies candidate facts with DOAJ, Crossref, and registry checks."""
        candidates = state.get("candidate_journals", {})
        logs = list(state.get("status_logs", []))

        verified_tally = 0
        for journal in candidates.values():
            if journal.verification_summary is None:
                self.verification.verify_journal(journal)
                verified_tally += 1

        logs.append(f"Completed evidence verification for {verified_tally} journal(s).")
        return {
            "candidate_journals": candidates,
            "status_logs": logs
        }

    def rank_and_score_node(self, state: ResearchAgentState) -> Dict[str, Any]:
        """Node 4: Computes multi-criteria rankings and explanations."""
        profile = state["profile"]
        candidates = list(state.get("candidate_journals", {}).values())
        logs = list(state.get("status_logs", []))

        ranked = self.ranking.rank_journals(profile, candidates)
        logs.append(f"Ranked {len(ranked)} journal(s) across semantic similarity, domain, and suitability.")

        return {
            "ranked_results": ranked,
            "status_logs": logs
        }

    def evaluate_termination(self, state: ResearchAgentState) -> str:
        """Determines whether to terminate search or refine queries for another loop."""
        thresholds = settings.thresholds
        ranked = state.get("ranked_results", [])
        current_iter = state.get("current_iteration", 0)
        api_calls = state.get("api_call_count", 0)
        no_progress = state.get("no_progress_count", 0)

        # Count candidates meeting minimum relevance score
        qualifying = sum(1 for r in ranked if r.research_relevance_score >= thresholds.min_relevance_score)

        if qualifying >= thresholds.min_candidates:
            return "terminate"

        if current_iter >= thresholds.max_iterations:
            return "terminate"

        if api_calls >= thresholds.max_api_calls:
            return "terminate"

        if no_progress >= thresholds.max_consecutive_no_progress:
            return "terminate"

        return "refine"

    def refine_queries_node(self, state: ResearchAgentState) -> Dict[str, Any]:
        """Node 5: Refines search queries based on top candidates' concept clusters."""
        ranked = state.get("ranked_results", [])
        logs = list(state.get("status_logs", []))

        new_queries = list(state.get("queries", []))
        if ranked:
            top_j = ranked[0].journal
            if top_j.subject_areas:
                refined_q = f"{state['profile'].domain} {' '.join(top_j.subject_areas[:2])}"
                if refined_q not in new_queries:
                    new_queries.append(refined_q)
                    logs.append(f"Refined search query: '{refined_q}'")

        return {
            "queries": new_queries,
            "status_logs": logs
        }

    def synthesize_summary_node(self, state: ResearchAgentState) -> Dict[str, Any]:
        """Node 6: Synthesizes final grounded research summary and submission advice."""
        profile = state["profile"]
        ranked = state.get("ranked_results", [])
        logs = list(state.get("status_logs", []))

        logs.append("Generating grounded research summary and tailored submission advice...")
        summary = self.llm.generate_research_summary(profile)

        # Generate advice for top 5 candidates
        for result in ranked[:5]:
            advice = self.llm.generate_journal_fit_advice(profile, result)
            result.confidence_notes = advice

        logs.append(f"Workflow complete. Finalized recommendations for {len(ranked)} journals.")

        return {
            "research_summary": summary,
            "is_terminated": True,
            "termination_reason": f"Completed with {len(ranked)} evaluated journals across {state.get('current_iteration', 1)} iteration(s).",
            "status_logs": logs
        }

    def _upsert_journal(self, store: Dict[str, JournalRecord], new_record: JournalRecord) -> None:
        """Merges new record into existing store using canonical keys and merge logic."""
        canonical_key = get_canonical_journal_key(new_record)

        if canonical_key in store:
            store[canonical_key] = merge_journal_records(store[canonical_key], new_record)
            return

        # Check for mergeable match across existing records
        for key, existing in list(store.items()):
            if can_merge_journals(existing, new_record):
                store[key] = merge_journal_records(existing, new_record)
                return

        # Add brand new journal
        new_record.compute_missing_fields()
        store[canonical_key] = new_record


def create_journal_finder_agent() -> Any:
    """Builds and compiles the LangGraph state machine."""
    workflow = JournalFinderWorkflow()
    builder = StateGraph(ResearchAgentState)

    # Add Nodes
    builder.add_node("generate_queries", workflow.generate_queries_node)
    builder.add_node("search_venues", workflow.search_venues_node)
    builder.add_node("verify_evidence", workflow.verify_evidence_node)
    builder.add_node("rank_and_score", workflow.rank_and_score_node)
    builder.add_node("refine_queries", workflow.refine_queries_node)
    builder.add_node("synthesize_summary", workflow.synthesize_summary_node)

    # Set Edges
    builder.set_entry_point("generate_queries")
    builder.add_edge("generate_queries", "search_venues")
    builder.add_edge("search_venues", "verify_evidence")
    builder.add_edge("verify_evidence", "rank_and_score")

    # Conditional Branching
    builder.add_conditional_edges(
        "rank_and_score",
        workflow.evaluate_termination,
        {
            "terminate": "synthesize_summary",
            "refine": "refine_queries"
        }
    )
    builder.add_edge("refine_queries", "search_venues")
    builder.add_edge("synthesize_summary", END)

    return builder.compile()
