"""Tests for research paper input validation and PDF text extraction."""

import pytest
import fitz  # PyMuPDF
from pydantic import ValidationError

from models.research import ResearchProfile, AccessPreference
from utils.pdf_extractor import extract_text_from_pdf_bytes, extract_metadata_from_text
from utils.text_processing import clean_text, generate_search_query_variations


def test_valid_research_profile_creation(sample_profile):
    """Verifies that a well-formed research profile is valid."""
    assert sample_profile.title.startswith("Deep Transfer Learning")
    assert len(sample_profile.keywords) == 4
    assert sample_profile.access_preference == AccessPreference.ANY
    assert sample_profile.max_apc_usd == 3000.0


def test_invalid_research_profile_empty_fields():
    """Verifies that empty title or abstract raises ValidationError."""
    with pytest.raises(ValidationError):
        ResearchProfile(title="", abstract="A study on AI.", keywords=["ai"])

    with pytest.raises(ValidationError):
        ResearchProfile(title="Valid Title", abstract="", keywords=["ai"])


def test_pdf_extraction_valid():
    """Generates an in-memory test PDF and verifies text extraction."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Title: Advanced Neural Radiance Fields\n\nAbstract: This paper introduces NeRF methods for 3D modeling."
    )
    pdf_bytes = doc.write()
    doc.close()

    result = extract_text_from_pdf_bytes(pdf_bytes)
    assert result["page_count"] == 1
    assert "Neural Radiance Fields" in result["full_text"]
    assert "3D modeling" in result["full_text"]


def test_pdf_extraction_corrupted_bytes():
    """Tests that corrupt PDF bytes fail gracefully without crash."""
    bad_bytes = b"not a valid pdf format at all 123456"
    result = extract_text_from_pdf_bytes(bad_bytes)
    assert result["page_count"] == 0
    assert result["full_text"] == ""
    assert result["error"] is not None


def test_pdf_metadata_extraction():
    """Tests identification of title, abstract, and sections from text."""
    sample_text = (
        "Adaptive Graph Neural Networks for Traffic Flow Prediction\n\n"
        "Abstract\n"
        "Accurate traffic forecasting is vital for smart city operations. "
        "In this study, we propose an adaptive dynamic graph convolution framework.\n\n"
        "Keywords: traffic flow, graph neural networks, spatiotemporal prediction"
    )
    meta = extract_metadata_from_text(sample_text)
    assert "Traffic Flow Prediction" in meta["title"]
    assert "traffic forecasting is vital" in meta["abstract"].lower()
    assert len(meta["keywords"]) >= 2


def test_query_variations_generation(sample_profile):
    """Verifies generation of diverse, non-empty query variations."""
    queries = generate_search_query_variations(
        title=sample_profile.title,
        keywords=sample_profile.keywords,
        domain=sample_profile.domain
    )
    assert len(queries) >= 3
    assert all(isinstance(q, str) and len(q) > 5 for q in queries)
    # Ensure no duplicates
    assert len(queries) == len(set(queries))
