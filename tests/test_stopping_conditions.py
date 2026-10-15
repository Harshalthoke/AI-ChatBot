"""Tests for LangGraph agent bounded loop termination conditions."""

import pytest
from unittest.mock import MagicMock
from agent.workflow import JournalFinderWorkflow
from config.settings import settings
from models.research import ResearchProfile
from models.journal import JournalRecord, JournalRankingResult


def test_stopping_condition_max_iterations(sample_profile):
    """Verifies loop terminates when current_iteration reaches max_iterations."""
    wf = JournalFinderWorkflow()
    state = {
        "profile": sample_profile,
        "current_iteration": settings.thresholds.max_iterations,
        "api_call_count": 5,
        "no_progress_count": 0,
        "ranked_results": []
    }
    decision = wf.evaluate_termination(state)
    assert decision == "terminate"


def test_stopping_condition_max_api_calls(sample_profile):
    """Verifies loop terminates when api_call_count exceeds max_api_calls."""
    wf = JournalFinderWorkflow()
    state = {
        "profile": sample_profile,
        "current_iteration": 1,
        "api_call_count": settings.thresholds.max_api_calls,
        "no_progress_count": 0,
        "ranked_results": []
    }
    decision = wf.evaluate_termination(state)
    assert decision == "terminate"


def test_stopping_condition_no_progress(sample_profile):
    """Verifies loop terminates after consecutive iterations without new journals."""
    wf = JournalFinderWorkflow()
    state = {
        "profile": sample_profile,
        "current_iteration": 2,
        "api_call_count": 6,
        "no_progress_count": settings.thresholds.max_consecutive_no_progress,
        "ranked_results": []
    }
    decision = wf.evaluate_termination(state)
    assert decision == "terminate"


def test_stopping_condition_sufficient_candidates(sample_profile, sample_candidates):
    """Verifies loop terminates early when target high-relevance candidate count is met."""
    wf = JournalFinderWorkflow()
    # Create sufficient high-scoring results
    qualifying_results = []
    for i in range(settings.thresholds.min_candidates + 1):
        j = sample_candidates[0].model_copy()
        qualifying_results.append(
            JournalRankingResult(
                rank=i + 1,
                journal=j,
                total_score=0.85,
                research_relevance_score=0.90,
                publication_suitability_score=0.80,
                evidence_completeness_score=0.75,
                recommendation_explanation="High match."
            )
        )

    state = {
        "profile": sample_profile,
        "current_iteration": 1,
        "api_call_count": 3,
        "no_progress_count": 0,
        "ranked_results": qualifying_results
    }
    decision = wf.evaluate_termination(state)
    assert decision == "terminate"


def test_stopping_condition_continues_when_incomplete(sample_profile):
    """Verifies loop continues to refine when budget remains and candidates are below threshold."""
    wf = JournalFinderWorkflow()
    state = {
        "profile": sample_profile,
        "current_iteration": 1,
        "api_call_count": 3,
        "no_progress_count": 0,
        "ranked_results": []  # 0 candidates
    }
    decision = wf.evaluate_termination(state)
    assert decision == "refine"
