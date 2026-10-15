"""Tests for journal evidence verification and anti-hallucination checks."""

import pytest
from unittest.mock import MagicMock

from services.verification_service import VerificationService
from models.journal import JournalRecord
from models.evidence import VerificationStatus, VerificationAspect


def test_verification_service_with_doaj_match():
    """Tests verification of open-access journal listed in DOAJ."""
    mock_doaj = MagicMock()
    mock_doaj.get_journal_by_issn.return_value = {
        "title": "Energies",
        "publisher": "MDPI",
        "is_oa": True,
        "apc_usd": 2400.0,
        "source_url": "https://doaj.org/toc/1996-1073"
    }
    mock_doaj.search_by_title_or_query.return_value = []

    mock_crossref = MagicMock()
    mock_crossref.get_journal_by_issn.return_value = {
        "title": "Energies",
        "publisher": "MDPI"
    }

    journal = JournalRecord(
        journal_id="1996-1073",
        title="Energies",
        issn_linking="1996-1073",
        publisher="MDPI",
        is_open_access=True,
        apc_usd=2400.0
    )

    service = VerificationService(doaj_service=mock_doaj, crossref_service=mock_crossref)
    summary = service.verify_journal(journal)

    assert summary.overall_status == VerificationStatus.VERIFIED
    assert summary.is_doaj_listed is True
    assert summary.verified_count >= 2


def test_verification_conflicting_publisher():
    """Tests detection of conflicting publisher evidence."""
    mock_doaj = MagicMock()
    mock_doaj.get_journal_by_issn.return_value = None
    mock_doaj.search_by_title_or_query.return_value = []

    mock_crossref = MagicMock()
    # Crossref returns a completely different publisher
    mock_crossref.get_journal_by_issn.return_value = {
        "title": "Solar Energy",
        "publisher": "Different Publishing Group"
    }

    journal = JournalRecord(
        journal_id="0038-092X",
        title="Solar Energy",
        issn_linking="0038-092X",
        publisher="Elsevier"  # Claimed publisher differs
    )

    service = VerificationService(doaj_service=mock_doaj, crossref_service=mock_crossref)
    summary = service.verify_journal(journal)

    # Should flag conflicting evidence
    assert summary.conflicting_count >= 1
    assert summary.overall_status == VerificationStatus.CONFLICTING_EVIDENCE
    assert len(summary.warnings) >= 1


def test_verification_unverified_no_issn():
    """Tests journal without valid ISSN falls back to NOT_VERIFIED with warnings."""
    mock_doaj = MagicMock()
    mock_doaj.get_journal_by_issn.return_value = None
    mock_doaj.search_by_title_or_query.return_value = []

    mock_crossref = MagicMock()
    mock_crossref.get_journal_by_issn.return_value = None

    journal = JournalRecord(
        journal_id="unregistered-journal",
        title="Unregistered Journal of AI"
    )

    service = VerificationService(doaj_service=mock_doaj, crossref_service=mock_crossref)
    summary = service.verify_journal(journal)

    assert summary.overall_status in [VerificationStatus.NOT_VERIFIED, VerificationStatus.REQUIRES_MANUAL_REVIEW]
    assert len(summary.warnings) >= 1
