"""Tests for report generation service (HTML, CSV, JSON, BibTeX)."""

import json
from pathlib import Path
from models.journal import JournalRankingResult
from services.report_service import ReportService


def test_report_service_exports(sample_profile, sample_candidates, tmp_path):
    """Verifies that HTML, CSV, JSON, and BibTeX reports export correctly."""
    service = ReportService(output_dir=tmp_path)
    session_id = "test-session-12345"

    ranked = [
        JournalRankingResult(
            journal=sample_candidates[0],
            rank=1,
            total_score=0.88,
            research_relevance_score=0.90,
            publication_suitability_score=0.85,
            evidence_completeness_score=0.89,
            suitability_explanation="High thematic alignment with solar forecasting.",
            confidence_notes="Direct matches found."
        )
    ]
    queries = ["solar irradiance forecasting", "renewable energy photovoltaics"]

    # 1. HTML Report
    html_content = service.generate_html_report(
        session_id=session_id,
        profile=sample_profile,
        ranked_results=ranked,
        queries_used=queries,
        iteration_count=2,
        stop_reason="Target candidates reached.",
        research_summary="Solid solar energy recommendation."
    )
    assert "<!DOCTYPE html>" in html_content
    assert "Solar Energy" in html_content
    assert (tmp_path / f"report_{session_id}.html").exists()

    # 2. CSV Report
    csv_path = service.export_csv(session_id, ranked)
    assert csv_path.exists()
    content_csv = csv_path.read_text(encoding="utf-8")
    assert "Solar Energy" in content_csv
    assert "0038-092X" in content_csv

    # 3. JSON Report
    json_path = service.export_json(
        session_id=session_id,
        profile=sample_profile,
        ranked_results=ranked,
        queries_used=queries,
        iteration_count=2,
        stop_reason="Target candidates reached.",
        research_summary="Solid solar energy recommendation."
    )
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["session_id"] == session_id
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["journal"]["title"] == "Solar Energy"

    # 4. BibTeX Report
    bib_path = service.export_bibtex(session_id, ranked)
    assert bib_path.exists()
    bib_content = bib_path.read_text(encoding="utf-8")
    assert "@periodical{" in bib_content
    assert "Solar Energy" in bib_content
    assert "Elsevier" in bib_content
