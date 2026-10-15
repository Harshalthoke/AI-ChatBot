"""Pytest fixtures for Research Journal Finder AI test suite."""

import pytest
from typing import Dict, Any, List
from models.research import ResearchProfile, AccessPreference
from models.journal import JournalRecord, RepresentativePublication
from models.evidence import VerificationStatus, JournalVerificationSummary, EvidenceRecord, VerificationAspect


@pytest.fixture
def sample_profile() -> ResearchProfile:
    """Returns a valid research profile for testing."""
    return ResearchProfile(
        title="Deep Transfer Learning for Renewable Solar Photovoltaic Generation Forecasting",
        abstract=(
            "Accurate short-term forecasting of solar photovoltaic generation is essential "
            "for power grid stability. In this work, we present a deep transfer learning model "
            "leveraging spatial-temporal convolutions and multi-head self-attention. Extensive "
            "experiments across 10 geographical regions demonstrate superior MAPE accuracy."
        ),
        keywords=["solar forecasting", "photovoltaics", "transfer learning", "deep learning"],
        domain="Engineering & Technology",
        access_preference=AccessPreference.ANY,
        max_apc_usd=3000.0,
        indexing_preferences=["DOAJ", "Scopus"]
    )


@pytest.fixture
def mock_openalex_works() -> List[Dict[str, Any]]:
    """Mock OpenAlex works response."""
    return [
        {
            "id": "https://openalex.org/W12345",
            "doi": "https://doi.org/10.1016/j.solener.2023.01.001",
            "work_title": "Solar irradiance forecasting using deep LSTM networks",
            "publication_year": 2023,
            "cited_by_count": 45,
            "venue_name": "Solar Energy",
            "venue_issn_l": "0038-092X",
            "venue_issns": ["0038-092X", "1471-2970"],
            "venue_publisher": "Elsevier",
            "is_oa": False,
            "apc_usd": 3500.0,
            "source_url": "https://doi.org/10.1016/j.solener.2023.01.001"
        },
        {
            "id": "https://openalex.org/W67890",
            "doi": "https://doi.org/10.3390/en16010001",
            "work_title": "Photovoltaic Power Prediction with Convolutional Attention",
            "publication_year": 2024,
            "cited_by_count": 12,
            "venue_name": "Energies",
            "venue_issn_l": "1996-1073",
            "venue_issns": ["1996-1073"],
            "venue_publisher": "MDPI",
            "is_oa": True,
            "apc_usd": 2400.0,
            "source_url": "https://doi.org/10.3390/en16010001"
        }
    ]


@pytest.fixture
def mock_crossref_works() -> List[Dict[str, Any]]:
    """Mock Crossref works response."""
    return [
        {
            "doi": "10.1016/j.apenergy.2023.120555",
            "work_title": "Applied transfer learning for regional renewable forecasting",
            "venue_name": "Applied Energy",
            "venue_issn_l": "0306-2619",
            "venue_issns": ["0306-2619"],
            "venue_publisher": "Elsevier",
            "publication_year": 2023,
            "source_url": "https://doi.org/10.1016/j.apenergy.2023.120555"
        }
    ]


@pytest.fixture
def sample_candidates() -> List[JournalRecord]:
    """Returns sample candidate journals for testing."""
    j1 = JournalRecord(
        journal_id="0038-092X",
        title="Solar Energy",
        issn_linking="0038-092X",
        issn_print="0038-092X",
        publisher="Elsevier",
        homepage_url="https://www.sciencedirect.com/journal/solar-energy",
        subject_areas=["Renewable Energy", "Solar Energy", "Engineering"],
        is_open_access=False,
        apc_usd=3500.0,
        representative_publications=[
            RepresentativePublication(
                title="Deep solar irradiance forecasting",
                publication_year=2023,
                cited_by_count=35
            )
        ]
    )

    j2 = JournalRecord(
        journal_id="1996-1073",
        title="Energies",
        issn_linking="1996-1073",
        issn_electronic="1996-1073",
        publisher="MDPI",
        homepage_url="https://www.mdpi.com/journal/energies",
        subject_areas=["Energy Engineering", "Power Systems", "Renewables"],
        is_open_access=True,
        apc_usd=2400.0,
        representative_publications=[
            RepresentativePublication(
                title="Photovoltaic generation prediction",
                publication_year=2024,
                cited_by_count=10
            )
        ]
    )

    return [j1, j2]
