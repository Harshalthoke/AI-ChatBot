"""Tests for journal deduplication, ISSN normalization, and distinct journal separation."""

import pytest
from models.journal import JournalRecord, RepresentativePublication
from utils.deduplication import (
    normalize_issn,
    canonical_title_slug,
    get_canonical_journal_key,
    can_merge_journals,
    merge_journal_records
)


def test_normalize_issn():
    """Tests proper hyphenation and normalization of ISSN formats."""
    assert normalize_issn("12345678") == "1234-5678"
    assert normalize_issn("1234-5678") == "1234-5678"
    assert normalize_issn("1234567x") == "1234-567X"
    assert normalize_issn("invalid") is None
    assert normalize_issn("") is None


def test_canonical_title_slug():
    """Tests creation of consistent slugs from journal titles."""
    assert canonical_title_slug("The Journal of Solar Energy") == "journal_of_solar_energy"
    assert canonical_title_slug("Journal of Solar Energy (Online)") == "journal_of_solar_energy"
    assert canonical_title_slug("IEEE Transactions on AI") == "ieee_transactions_on_ai"


def test_merge_journal_records_same_issn():
    """Verifies that records sharing an ISSN merge seamlessly."""
    j1 = JournalRecord(
        journal_id="0038-092X",
        title="Solar Energy",
        issn_linking="0038-092X",
        publisher="Elsevier",
        is_open_access=False,
        sources_contributed=["OpenAlex"]
    )
    j2 = JournalRecord(
        journal_id="0038-092X",
        title="Solar Energy (International)",
        issn_linking="0038-092X",
        homepage_url="https://www.sciencedirect.com/journal/solar-energy",
        apc_usd=3500.0,
        sources_contributed=["Crossref"]
    )

    assert can_merge_journals(j1, j2) is True
    merged = merge_journal_records(j1, j2)
    assert merged.publisher == "Elsevier"
    assert merged.homepage_url == "https://www.sciencedirect.com/journal/solar-energy"
    assert merged.apc_usd == 3500.0
    assert "OpenAlex" in merged.sources_contributed
    assert "Crossref" in merged.sources_contributed


def test_distinct_journals_different_issn_not_merged():
    """CRITICAL: Verifies similar titles with distinct ISSNs are NOT merged."""
    j1 = JournalRecord(
        journal_id="1111-2222",
        title="Journal of Clean Energy",
        issn_linking="1111-2222"
    )
    j2 = JournalRecord(
        journal_id="3333-4444",
        title="Journal of Clean Energy",
        issn_linking="3333-4444"
    )

    assert can_merge_journals(j1, j2) is False


def test_get_canonical_journal_key():
    """Verifies preference for ISSN over slug in canonical key."""
    j_with_issn = JournalRecord(
        journal_id="temp",
        title="Nature Energy",
        issn_linking="2058-7546"
    )
    assert get_canonical_journal_key(j_with_issn) == "issn:2058-7546"

    j_no_issn = JournalRecord(
        journal_id="temp",
        title="Nature Energy"
    )
    assert get_canonical_journal_key(j_no_issn) == "title:nature_energy"
