"""Multi-criteria ranking engine for candidate academic journals."""

import logging
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config.settings import settings, RankingWeights
from models.research import ResearchProfile, AccessPreference
from models.journal import JournalRecord, JournalRankingResult
from models.evidence import VerificationStatus
from utils.text_processing import calculate_jaccard_overlap, clean_text

logger = logging.getLogger(__name__)


class JournalRankingEngine:
    """Computes multi-dimensional suitability scores and grounded explanations for candidate journals."""

    def __init__(self, weights: Optional[RankingWeights] = None):
        self.weights = weights or settings.ranking_weights

    def rank_journals(
        self,
        profile: ResearchProfile,
        candidates: List[JournalRecord]
    ) -> List[JournalRankingResult]:
        """Ranks a list of candidate journals against the research profile."""
        if not candidates:
            return []

        # 1. Semantic similarities via TF-IDF + Cosine Similarity
        semantic_scores = self._compute_semantic_similarities(profile, candidates)

        results: List[JournalRankingResult] = []

        for idx, journal in enumerate(candidates):
            semantic_score = semantic_scores[idx]
            topic_score = self._compute_topic_overlap(profile, journal)
            domain_score = self._compute_domain_match(profile, journal)
            suitability_score, warnings = self._compute_publication_suitability(profile, journal)
            evidence_score = journal.evidence_completeness_ratio()

            # Research relevance is composite of semantic, topic, and domain
            research_relevance = (
                0.55 * semantic_score +
                0.30 * topic_score +
                0.15 * domain_score
            )
            research_relevance = float(np.clip(research_relevance, 0.0, 1.0))

            # Overall composite score according to configurable weights
            w = self.weights
            total_score = (
                w.weight_semantic_similarity * semantic_score +
                w.weight_topic_concept_match * topic_score +
                w.weight_domain_match * domain_score +
                w.weight_publication_suitability * suitability_score +
                w.weight_evidence_completeness * evidence_score
            )
            total_score = float(np.clip(total_score, 0.0, 1.0))

            # Grounded explanation
            explanation = self._build_grounded_explanation(
                journal,
                semantic_score,
                topic_score,
                domain_score,
                suitability_score,
                evidence_score
            )

            # Verification status
            v_status = (
                journal.verification_summary.overall_status
                if journal.verification_summary
                else VerificationStatus.NOT_VERIFIED
            )

            results.append(JournalRankingResult(
                journal=journal,
                rank=1,  # will be assigned after sorting
                research_relevance_score=round(research_relevance, 4),
                publication_suitability_score=round(suitability_score, 4),
                evidence_completeness_score=round(evidence_score, 4),
                semantic_similarity=round(semantic_score, 4),
                topic_concept_overlap=round(topic_score, 4),
                domain_match=round(domain_score, 4),
                verification_status=v_status,
                recommendation_explanation=explanation,
                mismatch_warnings=warnings,
                confidence_notes=f"Calculated from {len(journal.sources_contributed)} metadata source(s)."
            ))

        # Sort descending by composite score (stored in research_relevance + publication_suitability weighted)
        def sort_key(r: JournalRankingResult) -> float:
            return (
                self.weights.weight_semantic_similarity * r.semantic_similarity +
                self.weights.weight_topic_concept_match * r.topic_concept_overlap +
                self.weights.weight_domain_match * r.domain_match +
                self.weights.weight_publication_suitability * r.publication_suitability_score +
                self.weights.weight_evidence_completeness * r.evidence_completeness_score
            )

        # Calculate total_score and sort descending
        for item in results:
            item.total_score = round(sort_key(item), 4)

        results.sort(key=lambda r: r.total_score, reverse=True)

        # Assign ranks
        for i, item in enumerate(results, start=1):
            item.rank = i

        return results

    def _compute_semantic_similarities(
        self,
        profile: ResearchProfile,
        candidates: List[JournalRecord]
    ) -> List[float]:
        """Calculates TF-IDF cosine similarity between the paper and each journal's corpus."""
        paper_text = profile.full_text_representation()

        journal_texts = []
        for j in candidates:
            parts = [
                f"Title: {j.title}",
                f"Aims and Scope: {j.aims_and_scope or ''}",
                f"Subject Areas: {', '.join(j.subject_areas)}",
                f"Publisher: {j.publisher or ''}"
            ]
            if j.alternate_titles:
                parts.append(f"Alternate Titles: {', '.join(j.alternate_titles)}")
            if j.representative_publications:
                pub_titles = [p.title for p in j.representative_publications]
                parts.append(f"Recent Published Articles: {' | '.join(pub_titles)}")
            journal_texts.append("\n".join(parts))

        corpus = [paper_text] + journal_texts

        try:
            vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=5000,
                sublinear_tf=True
            )
            tfidf_matrix = vectorizer.fit_transform(corpus)
            paper_vec = tfidf_matrix[0:1]
            journal_vecs = tfidf_matrix[1:]
            similarities = cosine_similarity(paper_vec, journal_vecs)[0]
            return [float(np.clip(s, 0.0, 1.0)) for s in similarities]
        except Exception as e:
            logger.warning(f"TF-IDF similarity calculation failed, falling back to Jaccard: {e}")
            return [
                calculate_jaccard_overlap(paper_text, j_text)
                for j_text in journal_texts
            ]

    def _compute_topic_overlap(self, profile: ResearchProfile, journal: JournalRecord) -> float:
        """Evaluates concept and keyword overlap between paper and journal."""
        paper_terms = set(k.lower() for k in profile.keywords + profile.key_concepts)
        if not paper_terms:
            paper_terms = set(profile.title.lower().split())

        journal_terms = set(s.lower() for s in journal.subject_areas)
        for pub in journal.representative_publications:
            journal_terms.update(pub.title.lower().split())

        if not paper_terms or not journal_terms:
            return 0.3

        overlap = sum(
            1 for p_term in paper_terms
            if any(p_term in j_term or j_term in p_term for j_term in journal_terms)
        )
        ratio = overlap / max(len(paper_terms), 1)
        return float(np.clip(ratio, 0.0, 1.0))

    def _compute_domain_match(self, profile: ResearchProfile, journal: JournalRecord) -> float:
        """Calculates discipline alignment."""
        if not profile.domain or profile.domain.lower() == "general science":
            return 0.7  # neutral score when domain is open

        domain_lower = profile.domain.lower()
        journal_subjects_lower = [s.lower() for s in journal.subject_areas]

        # Direct containment check
        for subj in journal_subjects_lower:
            if domain_lower in subj or subj in domain_lower:
                return 1.0

        # Partial token match
        domain_tokens = set(domain_lower.split())
        matched = 0
        for subj in journal_subjects_lower:
            subj_tokens = set(subj.split())
            if domain_tokens.intersection(subj_tokens):
                matched += 1

        if matched > 0:
            return min(0.5 + (0.2 * matched), 0.9)

        # Journal title check
        title_lower = journal.title.lower()
        if any(tok in title_lower for tok in domain_tokens if len(tok) > 3):
            return 0.85

        return 0.35

    def _compute_publication_suitability(
        self,
        profile: ResearchProfile,
        journal: JournalRecord
    ) -> Tuple[float, List[str]]:
        """Evaluates user constraints (OA, APC budget, indexing) and accumulates mismatch warnings."""
        scores: List[float] = []
        warnings: List[str] = []

        # 1. Access Preference
        if profile.preferred_access == AccessPreference.OPEN_ACCESS:
            if journal.is_open_access is True:
                scores.append(1.0)
            elif journal.is_open_access is False:
                scores.append(0.2)
                warnings.append("Journal does not offer full Gold Open Access (subscription or hybrid venue).")
            else:
                scores.append(0.5)
                warnings.append("Open Access policy status is unconfirmed in public registry.")
        elif profile.preferred_access == AccessPreference.HYBRID_OR_SUBSCRIPTION:
            if journal.is_open_access is False or journal.is_open_access is None:
                scores.append(1.0)
            else:
                scores.append(0.5)
                warnings.append("Journal is fully Open Access, requiring APC fee for publication.")
        else:
            scores.append(1.0)  # ANY

        # 2. APC Budget
        if profile.max_apc_usd is not None:
            if journal.apc_usd is not None:
                if journal.apc_usd <= profile.max_apc_usd:
                    scores.append(1.0)
                else:
                    excess = journal.apc_usd - profile.max_apc_usd
                    penalty = max(0.1, 1.0 - (excess / max(profile.max_apc_usd, 500.0)))
                    scores.append(penalty)
                    warnings.append(
                        f"APC fee (${journal.apc_usd:,.0f} USD) exceeds specified author budget of ${profile.max_apc_usd:,.0f} USD."
                    )
            elif journal.is_open_access is True:
                # OA journal without listed APC
                scores.append(0.6)
                warnings.append("Journal is Open Access but exact APC fee is not listed in index. Verify fee schedule.")
            else:
                # Subscription without APC
                scores.append(1.0)
        else:
            scores.append(1.0)

        # 3. Indexing Preferences
        if profile.indexing_preferences:
            claimed_lower = [c.lower() for c in journal.indexing_claims]
            matched_indices = [
                idx_pref for idx_pref in profile.indexing_preferences
                if idx_pref.lower() in claimed_lower or any(idx_pref.lower() in s.lower() for s in journal.sources_contributed)
            ]
            if matched_indices:
                scores.append(1.0)
            else:
                scores.append(0.65)
                warnings.append(f"Not yet verified for requested index(es): {', '.join(profile.indexing_preferences)}.")
        else:
            scores.append(1.0)

        suitability = sum(scores) / max(len(scores), 1)
        return float(np.clip(suitability, 0.0, 1.0)), warnings

    def _build_grounded_explanation(
        self,
        journal: JournalRecord,
        semantic: float,
        topic: float,
        domain: float,
        suitability: float,
        evidence: float
    ) -> str:
        """Creates transparent, grounded natural-language rationale."""
        reasons = []

        if semantic >= 0.6:
            reasons.append("high textual and thematic similarity to the paper's title and abstract")
        elif semantic >= 0.4:
            reasons.append("moderate thematic alignment with research content")

        pub_count = len(journal.representative_publications)
        if pub_count > 0:
            reasons.append(f"a track record of publishing closely related research ({pub_count} relevant paper(s) indexed)")

        if journal.is_open_access is True:
            if journal.apc_usd == 0.0:
                reasons.append("Diamond Open Access model with zero APC author fees")
            elif journal.apc_usd:
                reasons.append(f"Open Access venue with verified APC of ${journal.apc_usd:,.0f}")
            else:
                reasons.append("Open Access publication options")

        if journal.metrics and journal.metrics.get("h_index"):
            reasons.append(f"established citation metrics (h-index: {journal.metrics.get('h_index')})")

        if not reasons:
            reasons.append("aligned subject scope and disciplinary focus")

        return f"Recommended based on {', '.join(reasons)}."
