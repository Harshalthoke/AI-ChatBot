"""Tests for scholarly search clients: OpenAlex, Crossref, DOAJ, retries, and rate limits."""

import pytest
import requests
from unittest.mock import patch, MagicMock

from services.openalex_service import OpenAlexService
from services.crossref_service import CrossrefService
from services.doaj_service import DOAJService


def test_openalex_search_works_success():
    """Tests successful OpenAlex works retrieval and data normalization."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "id": "https://openalex.org/W100",
                "doi": "https://doi.org/10.1000/182",
                "title": "Machine Learning for Solar Power",
                "publication_year": 2023,
                "cited_by_count": 50,
                "primary_location": {
                    "source": {
                        "display_name": "IEEE Transactions on Sustainable Energy",
                        "issn_l": "1949-3029",
                        "issn": ["1949-3029"],
                        "host_organization_name": "IEEE",
                        "is_oa": False
                    }
                },
                "open_access": {"is_oa": False},
                "apc_paid": {"value_usd": 2100}
            }
        ]
    }

    service = OpenAlexService()
    with patch.object(service.session, "get", return_value=mock_resp):
        results = service.search_works("solar forecasting", limit=5)
        assert len(results) == 1
        w = results[0]
        assert w["venue_name"] == "IEEE Transactions on Sustainable Energy"
        assert w["venue_issn_l"] == "1949-3029"
        assert w["venue_publisher"] == "IEEE"


def test_openalex_timeout_handling():
    """Tests that timeout exception is handled without crashing."""
    service = OpenAlexService()
    with patch.object(service.session, "get", side_effect=requests.exceptions.Timeout("Timeout")):
        results = service.search_works("query", limit=5)
        assert results == []


def test_crossref_search_success():
    """Tests Crossref search and normalization."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "items": [
                {
                    "DOI": "10.1016/j.solener.2023.01.001",
                    "title": ["A Hybrid Solar Forecaster"],
                    "container-title": ["Solar Energy"],
                    "ISSN": ["0038-092X"],
                    "publisher": "Elsevier BV",
                    "issued": {"date-parts": [[2023]]}
                }
            ]
        }
    }

    service = CrossrefService()
    with patch.object(service.session, "get", return_value=mock_resp):
        results = service.search_works_by_query("solar", limit=5)
        assert len(results) == 1
        assert results[0]["venue_name"] == "Solar Energy"
        assert results[0]["venue_publisher"] == "Elsevier BV"


def test_doaj_journal_lookup():
    """Tests DOAJ journal query matching by ISSN."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total": 1,
        "results": [
            {
                "bibjson": {
                    "title": "Energies",
                    "pissn": "1996-1073",
                    "eissn": "1996-1073",
                    "publisher": {"name": "MDPI"},
                    "apc": {"has_apc": True, "max": [{"price": 2400, "currency": "CHF"}]}
                }
            }
        ]
    }

    service = DOAJService()
    with patch.object(service.session, "get", return_value=mock_resp):
        info = service.get_journal_by_issn("1996-1073")
        assert info is not None
        assert info["journal_name"] == "Energies"
        assert info["is_open_access"] is True


def test_api_rate_limiting_429_handling():
    """Tests that HTTP 429 response is handled safely."""
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_429)

    service = OpenAlexService()
    with patch.object(service.session, "get", return_value=mock_429):
        results = service.search_works("random_query_never_cached_429_test", limit=5)
        assert results == []


def test_malformed_json_response_handling():
    """Tests that malformed non-JSON response is caught safely."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("No JSON object could be decoded")

    service = CrossrefService()
    with patch.object(service.session, "get", return_value=mock_resp):
        results = service.search_works_by_query("solar")
        assert results == []
