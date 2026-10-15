"""UI component for rendering academic journal recommendation cards."""

import streamlit as st
from typing import List
from models.journal import JournalRankingResult
from models.evidence import VerificationStatus


def render_verification_badge(status_str: str) -> None:
    """Renders a styled colored pill badge for verification status."""
    badge_colors = {
        "VERIFIED": ("#dcfce7", "#166534"),
        "NOT_VERIFIED": ("#fef9c3", "#854d0e"),
        "CONFLICTING_EVIDENCE": ("#fee2e2", "#991b1b"),
        "REQUIRES_MANUAL_REVIEW": ("#ffedd5", "#9a3412"),
        "UNAVAILABLE": ("#f1f5f9", "#475569")
    }
    bg, fg = badge_colors.get(status_str, ("#f1f5f9", "#475569"))
    st.markdown(
        f"""
        <span style="background-color: {bg}; color: {fg}; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 0.8rem; text-transform: uppercase;">
            {status_str.replace('_', ' ')}
        </span>
        """,
        unsafe_allow_html=True
    )


def render_journal_card(result: JournalRankingResult) -> None:
    """Renders a single comprehensive journal card with scores, evidence, and provenance."""
    journal = result.journal
    v_summary = journal.verification_summary
    v_status = v_summary.overall_status.value if v_summary else "NOT_VERIFIED"

    with st.container(border=True):
        # Header Row: Title & Badges
        col_title, col_score = st.columns([3, 1])
        with col_title:
            st.markdown(f"### #{result.rank}. {journal.title}")
            publisher_info = f"**Publisher:** {journal.publisher or 'Unknown'}"
            issn_info = f"**ISSN-L:** {journal.issn_linking or journal.get_primary_issn() or 'N/A'}"
            st.caption(f"{publisher_info} | {issn_info}")
        with col_score:
            st.metric(
                label="Overall Match",
                value=f"{result.total_score * 100:.1f}%",
                help="Composite weighted score across semantic relevance, topics, domain match, and constraints"
            )

        # Score breakdown metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.caption("Relevance")
            st.write(f"**{result.research_relevance_score * 100:.0f}%**")
        with c2:
            st.caption("Suitability")
            st.write(f"**{result.publication_suitability_score * 100:.0f}%**")
        with c3:
            st.caption("Evidence")
            st.write(f"**{result.evidence_completeness_score * 100:.0f}%**")
        with c4:
            st.caption("Verification")
            render_verification_badge(v_status)

        st.divider()

        # Explanation & Advisory
        st.markdown(f"**Fit Analysis:** {result.suitability_explanation}")
        if result.confidence_notes:
            st.info(f"💡 **Submission Advisory:** {result.confidence_notes}")

        # Details in expander
        with st.expander("🔍 View Journal Details & Provenance"):
            d1, d2 = st.columns(2)
            with d1:
                st.write("**Access & Fees:**")
                oa_text = "✅ Open Access" if journal.is_open_access else ("❌ Subscription / Hybrid" if journal.is_open_access is False else "❓ Unknown")
                st.write(f"- Status: {oa_text}")
                apc_text = f"${journal.apc_usd:,.0f}" if journal.apc_usd is not None else "Unknown / None reported"
                st.write(f"- Publication Fee (APC): {apc_text}")
                if journal.homepage_url:
                    st.write(f"- Official Homepage: [{journal.homepage_url}]({journal.homepage_url})")

            with d2:
                st.write("**Subject Areas & Indexing:**")
                if journal.subject_areas:
                    st.write(f"- Subjects: {', '.join(journal.subject_areas[:4])}")
                if v_summary:
                    st.write(f"- DOAJ Listed: {'Yes' if v_summary.is_doaj_listed else 'No'}")
                    if v_summary.warnings:
                        for w in v_summary.warnings:
                            st.warning(f"⚠️ {w}")

            # Representative published works
            if journal.representative_publications:
                st.write("**Representative Publications from Venue:**")
                for pub in journal.representative_publications[:3]:
                    doi_link = f"([DOI]({pub.source_url}))" if pub.source_url else ""
                    st.markdown(f"- *{pub.title}* ({pub.publication_year or 'N/A'}) {doi_link}")
