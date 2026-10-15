"""UI component for interactive journal comparison, multi-parameter filtering, and exports."""

import streamlit as st
import pandas as pd
from typing import List
from models.journal import JournalRankingResult
from services.report_service import ReportService


def render_comparison_view(
    ranked_results: List[JournalRankingResult],
    session_id: str
) -> None:
    """Renders interactive comparison table with filters, sorting, and export capabilities."""
    st.subheader("Journal Comparison & Evaluation Matrix")

    if not ranked_results:
        st.info("No journal recommendations available for comparison. Run a search first.")
        return

    # Filter controls
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        oa_filter = st.selectbox(
            "Access Model",
            ["All", "Open Access Only", "Subscription / Hybrid Only"]
        )
    with f_col2:
        max_fee = st.number_input(
            "Max APC Fee (USD)",
            min_value=0,
            max_value=10000,
            value=5000,
            step=250
        )
    with f_col3:
        min_score = st.slider(
            "Min Overall Match %",
            min_value=0,
            max_value=100,
            value=30
        )
    with f_col4:
        sort_by = st.selectbox(
            "Sort By",
            ["Total Match (Desc)", "Research Relevance (Desc)", "Publication Suitability (Desc)", "APC Fee (Asc)"]
        )

    # Filter items
    filtered: List[JournalRankingResult] = []
    for r in ranked_results:
        j = r.journal
        if oa_filter == "Open Access Only" and not j.is_open_access:
            continue
        if oa_filter == "Subscription / Hybrid Only" and j.is_open_access:
            continue
        if j.apc_usd is not None and j.apc_usd > max_fee:
            continue
        if (r.total_score * 100) < min_score:
            continue
        filtered.append(r)

    # Sort items
    if sort_by == "Total Match (Desc)":
        filtered.sort(key=lambda x: x.total_score, reverse=True)
    elif sort_by == "Research Relevance (Desc)":
        filtered.sort(key=lambda x: x.research_relevance_score, reverse=True)
    elif sort_by == "Publication Suitability (Desc)":
        filtered.sort(key=lambda x: x.publication_suitability_score, reverse=True)
    elif sort_by == "APC Fee (Asc)":
        filtered.sort(key=lambda x: (x.journal.apc_usd if x.journal.apc_usd is not None else 999999))

    st.caption(f"Showing {len(filtered)} of {len(ranked_results)} evaluated journals")

    # Build DataFrame
    rows = []
    for r in filtered:
        j = r.journal
        v_sum = j.verification_summary
        rows.append({
            "Rank": r.rank,
            "Journal Title": j.title,
            "Publisher": j.publisher or "Unknown",
            "Total Match": f"{r.total_score * 100:.1f}%",
            "Relevance": f"{r.research_relevance_score * 100:.0f}%",
            "Suitability": f"{r.publication_suitability_score * 100:.0f}%",
            "Open Access": "Yes" if j.is_open_access else ("No" if j.is_open_access is False else "Unknown"),
            "APC Fee": f"${j.apc_usd:,.0f}" if j.apc_usd is not None else "Unknown",
            "Verification": v_sum.overall_status.value if v_sum else "NOT_VERIFIED",
            "DOAJ": "Yes" if (v_sum and v_sum.is_doaj_listed) else "No"
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("No candidate journals match the selected filter criteria.")

    # Export Buttons
    st.divider()
    st.markdown("#### 📤 Export Recommendations")
    e_col1, e_col2, e_col3, e_col4 = st.columns(4)
    report_service = ReportService()

    with e_col1:
        csv_path = report_service.export_csv(session_id, ranked_results)
        with open(csv_path, "rb") as f:
            st.download_button(
                label="📥 Download CSV",
                data=f,
                file_name=f"journal_recommendations_{session_id[:8]}.csv",
                mime="text/csv",
                key="dl_csv"
            )
    with e_col2:
        report_file = report_service.output_dir / f"report_{session_id}.html"
        if report_file.exists():
            with open(report_file, "rb") as f:
                st.download_button(
                    label="📄 Download HTML",
                    data=f,
                    file_name=f"research_report_{session_id[:8]}.html",
                    mime="text/html",
                    key="dl_html"
                )
    with e_col3:
        json_file = report_service.output_dir / f"session_{session_id}.json"
        if json_file.exists():
            with open(json_file, "rb") as f:
                st.download_button(
                    label="💾 Download JSON",
                    data=f,
                    file_name=f"session_{session_id[:8]}.json",
                    mime="application/json",
                    key="dl_json"
                )
    with e_col4:
        bib_path = report_service.export_bibtex(session_id, ranked_results)
        with open(bib_path, "rb") as f:
            st.download_button(
                label="📚 Download BibTeX (.bib)",
                data=f,
                file_name=f"journals_{session_id[:8]}.bib",
                mime="application/x-bibtex",
                key="dl_bib"
            )

