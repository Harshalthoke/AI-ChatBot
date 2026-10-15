"""End-to-end integration tests for the LangGraph autonomous journal finder agent."""

import pytest
from unittest.mock import MagicMock
from agent.workflow import JournalFinderWorkflow, create_journal_finder_agent
from agent.state import ResearchAgentState
from langgraph.graph import StateGraph, END


def test_full_agent_workflow_integration(sample_profile, mock_openalex_works, mock_crossref_works):
    """Executes the full LangGraph state machine with mocked services and validates results."""
    mock_openalex = MagicMock()
    mock_openalex.search_works.return_value = mock_openalex_works
    mock_openalex.search_sources.return_value = []

    mock_crossref = MagicMock()
    mock_crossref.search_works_by_query.return_value = mock_crossref_works
    mock_crossref.get_journal_by_issn.return_value = {"publisher": "Elsevier"}

    mock_doaj = MagicMock()
    mock_doaj.check_journal_by_issn.return_value = None

    # Construct workflow with mocked services
    workflow = JournalFinderWorkflow(
        openalex_service=mock_openalex,
        crossref_service=mock_crossref
    )

    # Build graph
    builder = StateGraph(ResearchAgentState)
    builder.add_node("generate_queries", workflow.generate_queries_node)
    builder.add_node("search_venues", workflow.search_venues_node)
    builder.add_node("verify_evidence", workflow.verify_evidence_node)
    builder.add_node("rank_and_score", workflow.rank_and_score_node)
    builder.add_node("refine_queries", workflow.refine_queries_node)
    builder.add_node("synthesize_summary", workflow.synthesize_summary_node)

    builder.set_entry_point("generate_queries")
    builder.add_edge("generate_queries", "search_venues")
    builder.add_edge("search_venues", "verify_evidence")
    builder.add_edge("verify_evidence", "rank_and_score")
    builder.add_conditional_edges(
        "rank_and_score",
        workflow.evaluate_termination,
        {"terminate": "synthesize_summary", "refine": "refine_queries"}
    )
    builder.add_edge("refine_queries", "search_venues")
    builder.add_edge("synthesize_summary", END)

    app = builder.compile()

    initial_state: ResearchAgentState = {
        "profile": sample_profile,
        "queries": [],
        "candidate_journals": {},
        "ranked_results": [],
        "current_iteration": 0,
        "api_call_count": 0,
        "no_progress_count": 0,
        "status_logs": [],
        "is_terminated": False,
        "termination_reason": "",
        "research_summary": ""
    }

    final_state = app.invoke(initial_state)

    # Verify execution outputs
    assert final_state["is_terminated"] is True
    assert len(final_state["candidate_journals"]) >= 2
    assert len(final_state["ranked_results"]) >= 2
    assert len(final_state["status_logs"]) > 3
    assert final_state["research_summary"] != ""
    assert "Solar Energy" in [r.journal.title for r in final_state["ranked_results"]]


def test_agent_workflow_partial_results_on_api_failure(sample_profile):
    """Verifies that if one scholarly service fails, the agent continues and preserves partial results."""
    mock_openalex = MagicMock()
    mock_openalex.search_works.side_effect = Exception("OpenAlex connection failed")
    mock_openalex.search_sources.return_value = []

    mock_crossref = MagicMock()
    mock_crossref.search_works_by_query.return_value = [
        {
            "doi": "10.1000/182",
            "work_title": "Surviving Publication",
            "venue_name": "Resilient Journal of Science",
            "venue_issn_l": "9999-8888",
            "venue_issns": ["9999-8888"],
            "venue_publisher": "Academic Press",
            "publication_year": 2023,
            "source_url": "https://doi.org/10.1000/182"
        }
    ]

    workflow = JournalFinderWorkflow(
        openalex_service=mock_openalex,
        crossref_service=mock_crossref
    )

    # Manually invoke search_venues node to verify partial survival
    state: ResearchAgentState = {
        "profile": sample_profile,
        "queries": ["resilient engineering"],
        "candidate_journals": {},
        "ranked_results": [],
        "current_iteration": 0,
        "api_call_count": 0,
        "no_progress_count": 0,
        "status_logs": [],
        "is_terminated": False,
        "termination_reason": "",
        "research_summary": ""
    }

    # Should not crash and should return Crossref candidates
    res = workflow.search_venues_node(state)
    assert len(res["candidate_journals"]) == 1
    assert "issn:9999-8888" in res["candidate_journals"]

