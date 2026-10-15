"""UI component for main application dashboard overview and system status."""

import streamlit as st
from config.settings import settings
from database.repository import ResearchRepository


def render_dashboard_overview() -> None:
    """Renders the main dashboard landing page with stats, recent activity, and system health."""
    st.title("🎓 Research Journal Finder AI")
    st.markdown(
        """
        **Evidence-Grounded Autonomous Research Publishing Assistant**  
        Helps academic researchers discover, evaluate, and verify high-fit peer-reviewed publication venues 
        using live scholarly indices (OpenAlex, Crossref, DOAJ) with LangGraph iterative search control.
        """
    )

    # Key Features Banner
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        st.metric(label="Primary Source", value="OpenAlex API", delta="Live Index")
    with b2:
        st.metric(label="Registry Checks", value="DOAJ + Crossref", delta="Verified")
    with b3:
        st.metric(label="Agent Engine", value="LangGraph", delta="Bounded Loop")
    with b4:
        st.metric(label="Local Storage", value="SQLite", delta="Persistent")

    st.divider()

    # System Health & Configuration Status
    st.subheader("System Configuration & Health")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("#### ⚙️ Active Settings")
            st.write(f"- **Max Search Iterations:** `{settings.thresholds.max_iterations}`")
            st.write(f"- **Target Candidates:** `{settings.thresholds.min_candidates}`")
            st.write(f"- **Min Relevance Threshold:** `{settings.thresholds.min_relevance_score * 100:.0f}%`")
            st.write(f"- **LLM Provider:** `{settings.llm_provider.capitalize()}`")
            st.write(f"- **Database Path:** `{settings.db_path.name}`")

    with c2:
        with st.container(border=True):
            st.markdown("#### 🛡️ Anti-Hallucination & Evidence Policy")
            st.write("✅ **Grounding:** Every recommendation originates from real index queries.")
            st.write("✅ **No Inventions:** Metrics, fees, and indexing statuses are never fabricated.")
            st.write("✅ **Transparent Fallbacks:** Explicit verification states for all claims.")
            st.write("✅ **Bounded Control:** Max API calls and no-progress termination safeguards.")

    # Recent Sessions Table
    st.divider()
    st.subheader("Recent Research Sessions")
    repo = ResearchRepository()
    sessions = repo.list_sessions(limit=5)
    if sessions:
        s_data = []
        for s in sessions:
            s_data.append({
                "Date": s.get("created_at", "")[:16],
                "Paper Title": (s.get("title") or "Untitled")[:50],
                "Domain": s.get("domain") or "General",
                "Status": s.get("status"),
                "Iterations": s.get("iteration_count"),
                "Stop Reason": (s.get("stop_reason") or "N/A")[:35]
            })
        st.dataframe(s_data, use_container_width=True, hide_index=True)
    else:
        st.info("No prior research sessions recorded. Go to 'Find Journals' to start your first search!")
