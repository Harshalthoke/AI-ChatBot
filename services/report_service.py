"""Report generation service for research recommendations in HTML, CSV, and JSON formats."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

from config.settings import settings
from models.research import ResearchProfile
from models.journal import JournalRankingResult
from models.evidence import VerificationStatus

logger = logging.getLogger(__name__)


class ReportService:
    """Generates evidence-backed research recommendation reports in HTML, CSV, and JSON formats."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.reports_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html_report(
        self,
        session_id: str,
        profile: ResearchProfile,
        ranked_results: List[JournalRankingResult],
        queries_used: List[str],
        iteration_count: int,
        stop_reason: str,
        research_summary: Optional[str] = None
    ) -> str:
        """Generates a comprehensive, modern academic HTML report."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Build table rows for journals
        rows_html = []
        for r in ranked_results:
            j = r.journal
            v_summary = j.verification_summary
            v_status = v_summary.overall_status.value if v_summary else "NOT_VERIFIED"
            
            # Badge CSS class
            badge_class = {
                "VERIFIED": "badge-verified",
                "NOT_VERIFIED": "badge-unverified",
                "CONFLICTING_EVIDENCE": "badge-conflict",
                "REQUIRES_MANUAL_REVIEW": "badge-review",
                "UNAVAILABLE": "badge-unavailable"
            }.get(v_status, "badge-unverified")

            oa_label = "Open Access" if j.is_open_access else ("Subscription / Hybrid" if j.is_open_access is False else "Unknown")
            fee_label = f"${j.apc_usd:,.0f}" if j.apc_usd is not None else "Unknown / None reported"
            issn = j.get_primary_issn() or "N/A"
            link_html = f'<a href="{j.homepage_url}" target="_blank" rel="noopener">Official Link</a>' if j.homepage_url else "N/A"

            rows_html.append(f"""
            <tr>
                <td style="font-weight: 700; color: #1e293b;">#{r.rank}</td>
                <td>
                    <strong>{j.title}</strong><br>
                    <span style="font-size: 0.85em; color: #64748b;">Publisher: {j.publisher or 'Unknown'} | ISSN: {issn}</span><br>
                    <span style="font-size: 0.82em; color: #3b82f6;">{link_html}</span>
                </td>
                <td>
                    <span style="font-weight: 600; color: #0284c7;">{r.total_score * 100:.1f}%</span><br>
                    <span style="font-size: 0.8em; color: #64748b;">Relevance: {r.research_relevance_score * 100:.0f}%</span>
                </td>
                <td>{oa_label}<br><span style="font-size: 0.82em; color: #64748b;">Fee: {fee_label}</span></td>
                <td><span class="badge {badge_class}">{v_status}</span></td>
                <td style="font-size: 0.88em; color: #334155;">{r.suitability_explanation}</td>
            </tr>
            """)

        table_body = "\n".join(rows_html) if rows_html else "<tr><td colspan='6'>No journals evaluated.</td></tr>"

        queries_html = "".join([f"<li><code>{q}</code></li>" for q in queries_used])

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Academic Journal Recommendations - {profile.title[:50]}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #1e293b;
            background-color: #f8fafc;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        h1 {{
            color: #0f172a;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 12px;
            margin-top: 0;
        }}
        h2 {{
            color: #1e293b;
            margin-top: 32px;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 8px;
        }}
        .meta-box {{
            background: #f1f5f9;
            border-left: 4px solid #2563eb;
            padding: 16px 20px;
            border-radius: 6px;
            margin-bottom: 24px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-verified {{ background-color: #dcfce7; color: #166534; }}
        .badge-unverified {{ background-color: #fef9c3; color: #854d0e; }}
        .badge-conflict {{ background-color: #fee2e2; color: #991b1b; }}
        .badge-review {{ background-color: #ffedd5; color: #9a3412; }}
        .badge-unavailable {{ background-color: #f1f5f9; color: #475569; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
            font-size: 0.95rem;
        }}
        th, td {{
            text-align: left;
            padding: 12px 14px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        th {{
            background-color: #f8fafc;
            color: #475569;
            font-weight: 600;
        }}
        .warning-box {{
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-left: 4px solid #d97706;
            padding: 14px 18px;
            border-radius: 6px;
            margin-top: 24px;
            font-size: 0.9rem;
            color: #92400e;
        }}
        footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            font-size: 0.85rem;
            color: #64748b;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Research Journal Recommendation Report</h1>
        <div class="meta-box">
            <p><strong>Paper Title:</strong> {profile.title}</p>
            <p><strong>Research Domain:</strong> {profile.domain or 'General Science'} | <strong>Keywords:</strong> {', '.join(profile.keywords) if profile.keywords else 'None specified'}</p>
            <p><strong>Generated At:</strong> {timestamp} | <strong>Session ID:</strong> {session_id}</p>
            <p><strong>Agent Stopping Reason:</strong> {stop_reason} ({iteration_count} iterations completed)</p>
        </div>

        <h2>Executive Research Summary</h2>
        <p>{research_summary or (profile.abstract[:400] + '...' if len(profile.abstract) > 400 else profile.abstract)}</p>

        <h2>Ranked Journal Recommendations</h2>
        <table>
            <thead>
                <tr>
                    <th style="width: 50px;">Rank</th>
                    <th style="width: 250px;">Journal & Publisher</th>
                    <th style="width: 110px;">Overall Match</th>
                    <th style="width: 130px;">Access & Fee</th>
                    <th style="width: 140px;">Verification</th>
                    <th>Fit Analysis & Grounded Evidence</th>
                </tr>
            </thead>
            <tbody>
                {table_body}
            </tbody>
        </table>

        <h2>Search Methodology & Grounded Discovery</h2>
        <p>The autonomous agent queried authoritative scholarly venues via OpenAlex and Crossref APIs. Below are the targeted academic queries executed:</p>
        <ul>
            {queries_html}
        </ul>

        <div class="warning-box">
            <strong>Important Evidence Grounding Notice:</strong><br>
            All recommendations reflect scholarly records retrieved at the time of execution. Verification statuses rely on authoritative registries (DOAJ, Crossref, publisher metadata). Absence from an index does not imply predatory behavior. Researchers are advised to perform standard manual checks on submission guidelines and journal scope before final manuscript submission.
        </div>

        <footer>
            Generated by Research Journal Finder AI | Autonomous Multi-Criteria Evidence Engine
        </footer>
    </div>
</body>
</html>"""
        report_file = self.output_dir / f"report_{session_id}.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_content

    def export_csv(
        self,
        session_id: str,
        ranked_results: List[JournalRankingResult]
    ) -> Path:
        """Exports ranked journal results as a structured CSV file."""
        records = []
        for r in ranked_results:
            j = r.journal
            v_sum = j.verification_summary
            records.append({
                "Rank": r.rank,
                "Journal Title": j.title,
                "ISSN Linking": j.issn_linking or "",
                "ISSN Print": j.issn_print or "",
                "ISSN Electronic": j.issn_electronic or "",
                "Publisher": j.publisher or "",
                "Total Match Score": round(r.total_score, 4),
                "Research Relevance Score": round(r.research_relevance_score, 4),
                "Publication Suitability Score": round(r.publication_suitability_score, 4),
                "Evidence Completeness Score": round(r.evidence_completeness_score, 4),
                "Open Access": "Yes" if j.is_open_access else ("No" if j.is_open_access is False else "Unknown"),
                "APC USD": j.apc_usd if j.apc_usd is not None else "",
                "Verification Status": v_sum.overall_status.value if v_sum else "NOT_VERIFIED",
                "DOAJ Listed": "Yes" if (v_sum and v_sum.is_doaj_listed) else "No/Unverified",
                "Homepage URL": j.homepage_url or "",
                "Suitability Explanation": r.suitability_explanation,
                "Confidence Notes": r.confidence_notes or ""
            })

        df = pd.DataFrame(records)
        csv_path = self.output_dir / f"journals_{session_id}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        return csv_path

    def export_json(
        self,
        session_id: str,
        profile: ResearchProfile,
        ranked_results: List[JournalRankingResult],
        queries_used: List[str],
        iteration_count: int,
        stop_reason: str,
        research_summary: Optional[str] = None
    ) -> Path:
        """Exports complete recommendation session data as JSON."""
        data = {
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profile": profile.model_dump(),
            "execution": {
                "iteration_count": iteration_count,
                "stop_reason": stop_reason,
                "queries_used": queries_used,
                "research_summary": research_summary
            },
            "recommendations": [r.model_dump() for r in ranked_results]
        }
        json_path = self.output_dir / f"session_{session_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return json_path

    def export_bibtex(
        self,
        session_id: str,
        ranked_results: List[JournalRankingResult]
    ) -> Path:
        """Exports ranked journal candidates formatted as BibTeX entries for academic citation."""
        bib_entries = []
        for r in ranked_results:
            j = r.journal
            clean_issn = (j.get_primary_issn() or "").replace("-", "")
            cite_key = f"journal_{r.rank}_{clean_issn if clean_issn else 'rec'}"
            issn = j.get_primary_issn() or ""
            publisher = j.publisher or "Unknown"
            oa = "yes" if j.is_open_access else "no"

            entry = f"""@periodical{{{cite_key},
  title = {{{j.title}}},
  publisher = {{{publisher}}},
  issn = {{{issn}}},
  url = {{{j.homepage_url or ''}}},
  note = {{Rank: #{r.rank}, Match Score: {r.total_score * 100:.1f}%, Open Access: {oa}}}
}}"""
            bib_entries.append(entry)

        bib_content = "\n\n".join(bib_entries)
        bib_path = self.output_dir / f"journals_{session_id}.bib"
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(bib_content)
        return bib_path

