"""Tests for multi-criteria journal ranking engine, weights, and suitability scoring."""

import pytest
from services.ranking_service import JournalRankingEngine
from config.settings import RankingWeights
from models.research import ResearchProfile, AccessPreference
from models.journal import JournalRecord


def test_ranking_computes_normalized_scores(sample_profile, sample_candidates):
    """Verifies that all component and composite scores are within [0.0, 1.0]."""
    engine = JournalRankingEngine()
    ranked = engine.rank_journals(sample_profile, sample_candidates)

    assert len(ranked) == len(sample_candidates)
    for r in ranked:
        assert 0.0 <= r.total_score <= 1.0
        assert 0.0 <= r.research_relevance_score <= 1.0
        assert 0.0 <= r.publication_suitability_score <= 1.0
        assert 0.0 <= r.evidence_completeness_score <= 1.0
        assert isinstance(r.suitability_explanation, str)
        assert len(r.suitability_explanation) > 10


def test_ranking_budget_constraint_penalty(sample_profile, sample_candidates):
    """Verifies that an APC exceeding user budget lowers suitability score."""
    # Profile has max_apc_usd = 3000
    # j1 has apc_usd = 3500 (over budget)
    # j2 has apc_usd = 2400 (within budget)
    engine = JournalRankingEngine()
    ranked = engine.rank_journals(sample_profile, sample_candidates)

    r_map = {r.journal.title: r for r in ranked}
    assert r_map["Energies"].publication_suitability_score > r_map["Solar Energy"].publication_suitability_score


def test_ranking_weights_customization(sample_profile, sample_candidates):
    """Verifies that customized weights influence total composite ranking."""
    # Set strict constraints favor Energies
    sample_profile.preferred_access = AccessPreference.OPEN_ACCESS
    sample_profile.max_apc_usd = 2500.0

    heavy_suitability_weights = RankingWeights(
        weight_semantic_similarity=0.1,
        weight_topic_concept_match=0.1,
        weight_domain_match=0.1,
        weight_publication_suitability=0.6,
        weight_evidence_completeness=0.1
    )
    engine = JournalRankingEngine(weights=heavy_suitability_weights)
    ranked = engine.rank_journals(sample_profile, sample_candidates)

    assert len(ranked) == 2
    # Energies is OA and within budget, so suitability makes it #1
    assert ranked[0].journal.title == "Energies"

