"""UI component for monitoring live agent workflow progress and execution logs."""

import streamlit as st
from typing import List, Dict, Any, Optional


def render_activity_view(
    logs: List[str],
    current_iteration: int,
    max_iterations: int,
    candidate_count: int,
    api_calls: int,
    stop_reason: Optional[str] = None
) -> None:
    """Renders agent activity timeline, metrics, and event log."""
    st.subheader("Autonomous Agent Activity & Trace")

    # Metrics row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Current Iteration", f"{current_iteration} / {max_iterations}")
    with m2:
        st.metric("Candidates Discovered", candidate_count)
    with m3:
        st.metric("API Requests", api_calls)
    with m4:
        st.metric("Status", "Completed" if stop_reason else "Running / Idle")

    if stop_reason:
        st.success(f"🛑 **Agent Stop Reason:** {stop_reason}")

    # Event logs container
    st.markdown("#### Real-time Execution Log")
    if not logs:
        st.info("No agent activity recorded yet. Run a search to see agent reasoning and queries.")
        return

    with st.container(border=True, height=350):
        for log in logs:
            if "Iteration" in log:
                st.markdown(f"🔄 **{log}**")
            elif "Found" in log or "Completed" in log:
                st.markdown(f"✅ `{log}`")
            elif "Refined" in log or "Generated" in log:
                st.markdown(f"🔍 `{log}`")
            elif "Warning" in log or "error" in log.lower():
                st.markdown(f"⚠️ <span style='color: #d97706;'>{log}</span>", unsafe_allow_html=True)
            else:
                st.text(f"• {log}")
