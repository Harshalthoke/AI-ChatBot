"""Research Journal Finder AI - Main Streamlit Application."""

import os
import uuid
import logging
from typing import Dict, Any, List, Optional
import streamlit as st

import json
from config.settings import settings, SearchThresholds, RankingWeights
from models.research import ResearchProfile, AccessPreference
from models.journal import JournalRankingResult, JournalRecord
from models.evidence import VerificationStatus, JournalVerificationSummary
from database.repository import ResearchRepository
from services.report_service import ReportService
from utils.pdf_extractor import extract_text_from_pdf_bytes, extract_metadata_from_text
from agent.workflow import create_journal_finder_agent
from agent.state import ResearchAgentState
from ui.dashboard import render_dashboard_overview
from ui.journal_cards import render_journal_card, render_verification_badge
from ui.activity_view import render_activity_view
from ui.comparison import render_comparison_view

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Streamlit Page
st.set_page_config(
    page_title="Research Journal Finder AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern academic styling
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #f1f5f9;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "profile" not in st.session_state:
    st.session_state.profile = None
if "ranked_results" not in st.session_state:
    st.session_state.ranked_results = []
if "status_logs" not in st.session_state:
    st.session_state.status_logs = []
if "current_iteration" not in st.session_state:
    st.session_state.current_iteration = 0
if "stop_reason" not in st.session_state:
    st.session_state.stop_reason = None
if "research_summary" not in st.session_state:
    st.session_state.research_summary = ""
if "queries_used" not in st.session_state:
    st.session_state.queries_used = []

repo = ResearchRepository()
report_service = ReportService()

# Sidebar Navigation
st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio(
    "Select View:",
    [
        "1. Dashboard",
        "2. Find Journals",
        "3. Agent Activity",
        "4. Journal Comparison",
        "5. Verification Reports",
        "6. Search History",
        "7. Settings"
    ]
)

st.sidebar.divider()
st.sidebar.caption(f"**Session:** `{st.session_state.session_id[:8]}`")
st.sidebar.caption(f"**Engine:** LangGraph State Machine")
st.sidebar.caption(f"**LLM:** `{settings.llm_provider.capitalize()}`")


# -------------------------------------------------------------
# PAGE 1: DASHBOARD
# -------------------------------------------------------------
if page == "1. Dashboard":
    render_dashboard_overview()


# -------------------------------------------------------------
# PAGE 2: FIND JOURNALS
# -------------------------------------------------------------
elif page == "2. Find Journals":
    st.title("🔎 Find Target Academic Journals")
    st.markdown("Enter your paper details or upload a manuscript PDF to initiate evidence-grounded search.")

    with st.expander("📄 Upload Manuscript PDF (Optional)", expanded=True):
        uploaded_pdf = st.file_uploader("Upload PDF Paper", type=["pdf"])
        if uploaded_pdf is not None:
            with st.spinner("Extracting text and identifying metadata from PDF..."):
                pdf_bytes = uploaded_pdf.read()
                pdf_data = extract_text_from_pdf_bytes(pdf_bytes)
                if pdf_data["full_text"]:
                    meta = extract_metadata_from_text(pdf_data["full_text"])
                    st.success(f"Extracted {pdf_data['page_count']} pages ({len(pdf_data['full_text'])} characters).")
                    if meta.get("title") and not st.session_state.get("form_title"):
                        st.session_state["form_title"] = meta["title"]
                    if meta.get("abstract") and not st.session_state.get("form_abstract"):
                        st.session_state["form_abstract"] = meta["abstract"]

    # Submission Form
    with st.form("paper_input_form"):
        st.subheader("Paper Metadata & Publishing Preferences")
        c_title, c_domain = st.columns([2, 1])
        with c_title:
            paper_title = st.text_input(
                "Research Paper Title *",
                value=st.session_state.get("form_title", ""),
                placeholder="e.g., Deep Learning Approaches for High-Resolution Solar Radiation Forecasting"
            )
        with c_domain:
            paper_domain = st.selectbox(
                "Primary Research Domain",
                [
                    "Computer Science & AI",
                    "Engineering & Technology",
                    "Medicine & Life Sciences",
                    "Environmental Science & Energy",
                    "Physics & Mathematics",
                    "Social Sciences & Humanities",
                    "Economics & Business",
                    "Other / Interdisciplinary"
                ]
            )

        paper_abstract = st.text_area(
            "Abstract *",
            value=st.session_state.get("form_abstract", ""),
            height=160,
            placeholder="Paste your research abstract here to enable semantic matching..."
        )

        c_kw, c_oa, c_fee = st.columns([2, 1, 1])
        with c_kw:
            keywords_input = st.text_input(
                "Keywords (comma-separated)",
                placeholder="e.g., deep learning, solar forecasting, irradiance, lstm"
            )
        with c_oa:
            access_pref = st.selectbox(
                "Open Access Requirement",
                ["Any Access Model", "Open Access Only", "Subscription / Hybrid Only"]
            )
        with c_fee:
            max_fee_input = st.number_input(
                "Max Budget (USD)",
                min_value=0,
                max_value=12000,
                value=3500,
                step=250
            )

        c_idx1, c_idx2, c_idx3 = st.columns(3)
        with c_idx1:
            req_doaj = st.checkbox("Require DOAJ Listed", value=False)
        with c_idx2:
            req_scopus = st.checkbox("Check Scopus Coverage", value=True)
        with c_idx3:
            req_wos = st.checkbox("Check Web of Science", value=False)

        submit_btn = st.form_submit_button("🚀 Find Candidate Journals", use_container_width=True)

    if submit_btn:
        if not paper_title.strip() or not paper_abstract.strip():
            st.error("Please provide both a research title and an abstract to proceed.")
        else:
            # Map preferences
            oa_map = {
                "Any Access Model": AccessPreference.ANY,
                "Open Access Only": AccessPreference.OPEN_ACCESS_ONLY,
                "Subscription / Hybrid Only": AccessPreference.SUBSCRIPTION_ONLY
            }
            indexing_reqs = []
            if req_doaj:
                indexing_reqs.append("DOAJ")
            if req_scopus:
                indexing_reqs.append("Scopus")
            if req_wos:
                indexing_reqs.append("Web of Science")

            kw_list = [k.strip() for k in keywords_input.split(",") if k.strip()]

            profile = ResearchProfile(
                title=paper_title.strip(),
                abstract=paper_abstract.strip(),
                keywords=kw_list,
                domain=paper_domain,
                access_preference=oa_map[access_pref],
                max_apc_usd=float(max_fee_input) if max_fee_input > 0 else None,
                indexing_preferences=indexing_reqs
            )

            st.session_state.profile = profile
            st.session_state.session_id = str(uuid.uuid4())
            sid = st.session_state.session_id

            # Save initial session in SQLite
            repo.create_session(session_id=sid, status="RUNNING")
            repo.save_profile(session_id=sid, profile=profile)

            # Execution with live progress
            st.divider()
            status_container = st.status("🤖 Autonomous Agent Executing Search & Verification...", expanded=True)
            with status_container:
                st.write("Initializing LangGraph state machine...")
                agent = create_journal_finder_agent()

                initial_state: ResearchAgentState = {
                    "profile": profile,
                    "queries": [],
                    "candidate_journals": {},
                    "ranked_results": [],
                    "current_iteration": 0,
                    "api_call_count": 0,
                    "no_progress_count": 0,
                    "status_logs": ["Agent workflow initialized."],
                    "is_terminated": False,
                    "termination_reason": "",
                    "research_summary": ""
                }

                st.write("Querying scholarly databases (OpenAlex, Crossref) and verifying facts...")
                try:
                    final_state = agent.invoke(initial_state)

                    ranked = final_state.get("ranked_results", [])
                    candidates = final_state.get("candidate_journals", {})
                    logs = final_state.get("status_logs", [])
                    iter_count = final_state.get("current_iteration", 1)
                    api_calls = final_state.get("api_call_count", 0)
                    stop_msg = final_state.get("termination_reason", "Completed.")
                    summary_text = final_state.get("research_summary", "")

                    # Persist run in SQLite
                    repo.save_candidates(sid, candidates)
                    repo.save_verifications(sid, candidates)
                    repo.save_rankings(sid, ranked)
                    repo.save_logs(sid, logs)
                    repo.update_session_completion(
                        session_id=sid,
                        status="COMPLETED",
                        stop_reason=stop_msg,
                        iteration_count=iter_count,
                        api_call_count=api_calls,
                        research_summary=summary_text
                    )

                    # Generate static reports
                    report_service.generate_html_report(
                        session_id=sid,
                        profile=profile,
                        ranked_results=ranked,
                        queries_used=final_state.get("queries", []),
                        iteration_count=iter_count,
                        stop_reason=stop_msg,
                        research_summary=summary_text
                    )
                    report_service.export_csv(sid, ranked)
                    report_service.export_json(
                        session_id=sid,
                        profile=profile,
                        ranked_results=ranked,
                        queries_used=final_state.get("queries", []),
                        iteration_count=iter_count,
                        stop_reason=stop_msg,
                        research_summary=summary_text
                    )

                    # Update UI session state
                    st.session_state.ranked_results = ranked
                    st.session_state.status_logs = logs
                    st.session_state.current_iteration = iter_count
                    st.session_state.stop_reason = stop_msg
                    st.session_state.research_summary = summary_text
                    st.session_state.queries_used = final_state.get("queries", [])

                    status_container.update(
                        label=f"Search Finished! Evaluated {len(candidates)} candidates, ranked {len(ranked)} journals.",
                        state="complete"
                    )

                except Exception as e:
                    logger.exception(f"Error during agent execution: {e}")
                    status_container.update(label=f"Workflow halted with error: {e}", state="error")
                    st.error(f"Execution error: {e}")

    # Display Results if available
    if st.session_state.ranked_results:
        st.divider()
        st.subheader(f"Top Recommended Journals ({len(st.session_state.ranked_results)} evaluated)")
        for result in st.session_state.ranked_results:
            render_journal_card(result)


# -------------------------------------------------------------
# PAGE 3: AGENT ACTIVITY
# -------------------------------------------------------------
elif page == "3. Agent Activity":
    render_activity_view(
        logs=st.session_state.status_logs,
        current_iteration=st.session_state.current_iteration,
        max_iterations=settings.thresholds.max_iterations,
        candidate_count=len(st.session_state.ranked_results),
        api_calls=len(st.session_state.status_logs),
        stop_reason=st.session_state.stop_reason
    )


# -------------------------------------------------------------
# PAGE 4: JOURNAL COMPARISON
# -------------------------------------------------------------
elif page == "4. Journal Comparison":
    render_comparison_view(
        ranked_results=st.session_state.ranked_results,
        session_id=st.session_state.session_id
    )


# -------------------------------------------------------------
# PAGE 5: VERIFICATION REPORTS
# -------------------------------------------------------------
elif page == "5. Verification Reports":
    st.title("🛡️ Evidence & Verification Audit")
    st.markdown("Detailed verification checks, provenance records, and registry compliance audit.")

    if not st.session_state.ranked_results:
        st.info("No verified journals in current session. Run a search to inspect verification evidence.")
    else:
        for r in st.session_state.ranked_results:
            j = r.journal
            v_sum = j.verification_summary
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"#### {j.title}")
                    st.caption(f"Publisher: {j.publisher or 'Unknown'} | Primary ISSN: {j.get_primary_issn() or 'N/A'}")
                with c2:
                    st.write("**Overall Status:**")
                    render_verification_badge(v_sum.overall_status.value if v_sum else "NOT_VERIFIED")

                if v_sum:
                    v_col1, v_col2, v_col3 = st.columns(3)
                    with v_col1:
                        st.metric("Checks Verified", v_sum.verified_count)
                    with v_col2:
                        st.metric("Conflicting Evidence", v_sum.conflicting_count)
                    with v_col3:
                        st.metric("Requires Review", v_sum.requires_review_count)

                    st.markdown("##### Specific Registry Checks")
                    for aspect, record in v_sum.checks.items():
                        st.write(f"- **{aspect.replace('_', ' ').title()}:** `{record.status.value}` ({record.source_name})")
                        if record.notes:
                            st.caption(f"  *Notes:* {record.notes}")

                    if v_sum.warnings:
                        st.markdown("##### Verification Warnings")
                        for w in v_sum.warnings:
                            st.warning(f"⚠️ {w}")
                else:
                    st.info("Verification summary not yet generated for this journal.")


# -------------------------------------------------------------
# PAGE 6: SEARCH HISTORY
# -------------------------------------------------------------
elif page == "6. Search History":
    st.title("📜 Research Session History")
    st.markdown("View and reload past research sessions stored in SQLite database.")

    sessions = repo.list_sessions(limit=30)
    if not sessions:
        st.info("No prior research sessions stored in local database.")
    else:
        for s in sessions:
            with st.container(border=True):
                col_info, col_actions = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**{s.get('title') or 'Untitled Paper'}**")
                    st.caption(
                        f"Session ID: `{s['session_id'][:8]}...` | Date: {s['created_at']} | "
                        f"Status: `{s['status']}` | Iterations: {s['iteration_count']}"
                    )
                    if s.get("stop_reason"):
                        st.text(f"Stop Reason: {s['stop_reason']}")
                with col_actions:
                    btn_load, btn_del = st.columns(2)
                    with btn_load:
                        if st.button("📂 Load", key=f"load_{s['session_id']}"):
                            details = repo.get_session_details(s["session_id"])
                            if details:
                                st.session_state.session_id = s["session_id"]
                                if details.get("profile"):
                                    p = details["profile"]
                                    st.session_state.profile = ResearchProfile(
                                        title=p.get("title") or "",
                                        abstract=p.get("abstract") or "",
                                        keywords=json.loads(p.get("keywords") or "[]"),
                                        domain=p.get("domain") or "General",
                                        methodology=p.get("methodology"),
                                        access_preference=AccessPreference(p.get("access_preference")) if p.get("access_preference") else AccessPreference.ANY,
                                        max_apc_usd=p.get("max_apc_usd"),
                                        indexing_preferences=json.loads(p.get("indexing_preferences") or "[]")
                                    )
                                    st.session_state["form_title"] = p.get("title", "")
                                    st.session_state["form_abstract"] = p.get("abstract", "")

                                loaded_results = []
                                for r in details.get("rankings", []):
                                    v_status_str = r.get("verify_status") or "NOT_VERIFIED"
                                    try:
                                        v_status = VerificationStatus(v_status_str)
                                    except Exception:
                                        v_status = VerificationStatus.NOT_VERIFIED

                                    v_summary = JournalVerificationSummary(
                                        journal_id=r.get("journal_key", ""),
                                        overall_status=v_status
                                    )
                                    journal = JournalRecord(
                                        journal_id=r.get("journal_key", ""),
                                        title=r.get("journal_title") or "Unknown",
                                        publisher=r.get("publisher"),
                                        homepage_url=r.get("homepage_url"),
                                        issn_linking=r.get("issn_linking"),
                                        is_open_access=bool(r.get("is_open_access")) if r.get("is_open_access") is not None else None,
                                        apc_usd=r.get("apc_usd"),
                                        verification_summary=v_summary
                                    )
                                    ranking_res = JournalRankingResult(
                                        journal=journal,
                                        rank=r.get("rank_position", 1),
                                        total_score=r.get("total_score", 0.0),
                                        research_relevance_score=r.get("research_relevance_score", 0.0),
                                        publication_suitability_score=r.get("publication_suitability_score", 0.0),
                                        evidence_completeness_score=r.get("evidence_completeness_score", 0.0),
                                        suitability_explanation=r.get("explanation") or "",
                                        confidence_notes=r.get("confidence_notes") or ""
                                    )
                                    loaded_results.append(ranking_res)

                                st.session_state.ranked_results = loaded_results
                                st.session_state.status_logs = [l["log_message"] for l in details.get("logs", [])]
                                sess_info = details.get("session", {})
                                st.session_state.current_iteration = sess_info.get("iteration_count", 0)
                                st.session_state.stop_reason = sess_info.get("stop_reason")
                                st.session_state.research_summary = sess_info.get("research_summary") or ""
                                st.toast(f"Session {s['session_id'][:8]} loaded successfully!")
                                st.rerun()
                    with btn_del:
                        if st.button("🗑️ Delete", key=f"del_{s['session_id']}"):
                            repo.delete_session(s["session_id"])
                            st.toast("Session deleted.")
                            st.rerun()


# -------------------------------------------------------------
# PAGE 7: SETTINGS
# -------------------------------------------------------------
elif page == "7. Settings":
    st.title("⚙️ Engine Configuration & API Settings")
    st.markdown("Tune search thresholds, ranking weights, and external scholarly provider credentials.")

    with st.form("settings_form"):
        st.subheader("1. Agent Search & Stopping Thresholds")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            max_iter = st.slider("Max Iterations", 1, 10, settings.thresholds.max_iterations)
            min_cands = st.slider("Target Minimum Candidates", 1, 30, settings.thresholds.min_candidates)
        with col_t2:
            min_rel = st.slider("Min Research Relevance Threshold", 0.0, 1.0, float(settings.thresholds.min_relevance_score))
            max_calls = st.slider("Max API Requests Budget", 10, 150, settings.thresholds.max_api_calls)

        st.divider()
        st.subheader("2. Multi-Criteria Ranking Weights")
        w1, w2, w3 = st.columns(3)
        with w1:
            w_sem = st.slider("Semantic Similarity", 0.0, 1.0, float(settings.ranking_weights.weight_semantic_similarity))
            w_top = st.slider("Topic / Concept Overlap", 0.0, 1.0, float(settings.ranking_weights.weight_topic_concept_match))
        with w2:
            w_dom = st.slider("Domain Match", 0.0, 1.0, float(settings.ranking_weights.weight_domain_match))
            w_sui = st.slider("Publication Suitability", 0.0, 1.0, float(settings.ranking_weights.weight_publication_suitability))
        with w3:
            w_evi = st.slider("Evidence Completeness", 0.0, 1.0, float(settings.ranking_weights.weight_evidence_completeness))

        st.divider()
        st.subheader("3. Scholarly API & LLM Integration")
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            o_email = st.text_input("OpenAlex Polite Email", value=settings.openalex_email)
            cr_email = st.text_input("Crossref Polite Email", value=settings.crossref_email)
        with c_p2:
            provider = st.selectbox(
                "LLM Provider",
                ["fallback", "gemini", "openai", "ollama"],
                index=["fallback", "gemini", "openai", "ollama"].index(settings.llm_provider) if settings.llm_provider in ["fallback", "gemini", "openai", "ollama"] else 0
            )

        save_settings_btn = st.form_submit_button("💾 Save Settings", use_container_width=True)
        if save_settings_btn:
            settings.thresholds.max_iterations = max_iter
            settings.thresholds.min_candidates = min_cands
            settings.thresholds.min_relevance_score = min_rel
            settings.thresholds.max_api_calls = max_calls

            settings.ranking_weights.weight_semantic_similarity = w_sem
            settings.ranking_weights.weight_topic_concept_match = w_top
            settings.ranking_weights.weight_domain_match = w_dom
            settings.ranking_weights.weight_publication_suitability = w_sui
            settings.ranking_weights.weight_evidence_completeness = w_evi

            settings.openalex_email = o_email
            settings.crossref_email = cr_email
            settings.llm_provider = provider
            st.success("Settings updated successfully!")
