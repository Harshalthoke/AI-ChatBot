"""Data access repository for Research Journal Finder AI."""

import json
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from database.db import get_db_connection, init_database
from models.research import ResearchProfile, AccessPreference
from models.journal import JournalRecord, JournalRankingResult, RepresentativePublication
from models.evidence import VerificationStatus, JournalVerificationSummary, EvidenceRecord
from utils.deduplication import get_canonical_journal_key

logger = logging.getLogger(__name__)


class ResearchRepository:
    """Handles persistence and retrieval of research sessions and journal records."""

    def __init__(self):
        init_database()

    def create_session(
        self,
        session_id: Optional[str] = None,
        status: str = "IN_PROGRESS"
    ) -> str:
        """Creates a new research session entry."""
        sid = session_id or str(uuid.uuid4())
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO research_sessions (session_id, status, created_at, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (sid, status)
            )
        return sid

    def update_session_completion(
        self,
        session_id: str,
        status: str,
        stop_reason: str,
        iteration_count: int,
        api_call_count: int,
        research_summary: Optional[str] = None
    ) -> None:
        """Updates session completion status and statistics."""
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE research_sessions
                SET status = ?,
                    stop_reason = ?,
                    iteration_count = ?,
                    api_call_count = ?,
                    research_summary = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (status, stop_reason, iteration_count, api_call_count, research_summary, session_id)
            )

    def save_profile(self, session_id: str, profile: ResearchProfile) -> None:
        """Saves research profile associated with a session."""
        pid = str(uuid.uuid4())
        kw_str = json.dumps(profile.keywords)
        idx_str = json.dumps(profile.indexing_preferences)
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO research_profiles (
                    profile_id, session_id, title, abstract, keywords, domain,
                    methodology, access_preference, max_apc_usd, indexing_preferences
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid, session_id, profile.title, profile.abstract, kw_str,
                    profile.domain, profile.methodology,
                    profile.access_preference.value if profile.access_preference else None,
                    profile.max_apc_usd, idx_str
                )
            )

    def save_candidates(self, session_id: str, candidates: Dict[str, JournalRecord]) -> None:
        """Saves all candidate journals discovered during the session."""
        with get_db_connection() as conn:
            for key, j in candidates.items():
                record_id = f"{session_id}_{key}"
                conn.execute(
                    """
                    INSERT INTO candidate_journals (
                        record_id, session_id, canonical_key, title, issn_linking,
                        issn_print, issn_electronic, publisher, homepage_url,
                        subject_areas, is_open_access, apc_usd, metrics_json,
                        sources_contributed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(record_id) DO UPDATE SET
                        is_open_access=excluded.is_open_access,
                        apc_usd=excluded.apc_usd,
                        homepage_url=excluded.homepage_url
                    """,
                    (
                        record_id, session_id, key, j.title, j.issn_linking,
                        j.issn_print, j.issn_electronic, j.publisher,
                        j.homepage_url, json.dumps(j.subject_areas),
                        1 if j.is_open_access else (0 if j.is_open_access is False else None),
                        j.apc_usd, json.dumps(j.metrics),
                        json.dumps(j.sources_contributed)
                    )
                )

    def save_verifications(self, session_id: str, candidates: Dict[str, JournalRecord]) -> None:
        """Saves verification results for all verified candidates."""
        with get_db_connection() as conn:
            for key, j in candidates.items():
                summary = j.verification_summary
                if not summary:
                    continue
                check_id = f"{session_id}_{key}_verify"
                is_doaj = 1 if (
                    "doaj_listing" in summary.checks and 
                    summary.checks["doaj_listing"].status == VerificationStatus.VERIFIED
                ) else 0

                inconsistencies = [
                    f"{c.aspect.value}: {c.claimed_value} != {c.verified_value}"
                    for c in summary.checks.values()
                    if c.status == VerificationStatus.CONFLICTING_EVIDENCE
                ]

                conn.execute(
                    """
                    INSERT INTO verification_checks (
                        check_id, session_id, journal_key, status, is_doaj_listed,
                        inconsistencies, warnings, items_verified, items_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(check_id) DO UPDATE SET
                        status=excluded.status,
                        is_doaj_listed=excluded.is_doaj_listed,
                        warnings=excluded.warnings
                    """,
                    (
                        check_id, session_id, key, summary.overall_status.value,
                        is_doaj,
                        json.dumps(inconsistencies),
                        json.dumps(summary.warnings),
                        summary.verified_count, len(summary.checks)
                    )
                )

    def save_rankings(self, session_id: str, rankings: List[JournalRankingResult]) -> None:
        """Saves ranked journal recommendations."""
        with get_db_connection() as conn:
            for r in rankings:
                key = get_canonical_journal_key(r.journal)
                rid = f"{session_id}_{key}_rank"
                conn.execute(
                    """
                    INSERT INTO ranking_results (
                        ranking_id, session_id, journal_key, rank_position,
                        total_score, research_relevance_score,
                        publication_suitability_score, evidence_completeness_score,
                        explanation, confidence_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ranking_id) DO UPDATE SET
                        rank_position=excluded.rank_position,
                        total_score=excluded.total_score,
                        explanation=excluded.explanation,
                        confidence_notes=excluded.confidence_notes
                    """,
                    (
                        rid, session_id, key, r.rank, r.total_score,
                        r.research_relevance_score, r.publication_suitability_score,
                        r.evidence_completeness_score, r.suitability_explanation,
                        r.confidence_notes
                    )
                )

    def save_logs(self, session_id: str, logs: List[str]) -> None:
        """Saves agent execution event logs."""
        with get_db_connection() as conn:
            for log in logs:
                conn.execute(
                    "INSERT INTO agent_logs (session_id, log_message) VALUES (?, ?)",
                    (session_id, log)
                )

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists recent research sessions with profile titles."""
        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.session_id, s.created_at, s.status, s.stop_reason,
                       s.iteration_count, s.api_call_count, p.title, p.domain
                FROM research_sessions s
                LEFT JOIN research_profiles p ON s.session_id = p.session_id
                ORDER BY s.created_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> None:
        """Deletes a research session and all associated cascade records."""
        with get_db_connection() as conn:
            conn.execute("DELETE FROM research_sessions WHERE session_id = ?", (session_id,))

    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full session history including profile, rankings, and logs."""
        with get_db_connection() as conn:
            s_row = conn.execute(
                "SELECT * FROM research_sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            if not s_row:
                return None

            p_row = conn.execute(
                "SELECT * FROM research_profiles WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            rank_rows = conn.execute(
                """
                SELECT r.*, c.title as journal_title, c.publisher, c.homepage_url,
                       c.issn_linking, c.is_open_access, c.apc_usd, v.status as verify_status
                FROM ranking_results r
                LEFT JOIN candidate_journals c
                    ON r.session_id = c.session_id AND r.journal_key = c.canonical_key
                LEFT JOIN verification_checks v
                    ON r.session_id = v.session_id AND r.journal_key = v.journal_key
                WHERE r.session_id = ?
                ORDER BY r.rank_position ASC
                """,
                (session_id,)
            ).fetchall()

            log_rows = conn.execute(
                "SELECT log_message, created_at FROM agent_logs WHERE session_id = ? ORDER BY log_id ASC",
                (session_id,)
            ).fetchall()

            return {
                "session": dict(s_row),
                "profile": dict(p_row) if p_row else None,
                "rankings": [dict(r) for r in rank_rows],
                "logs": [dict(l) for l in log_rows]
            }
