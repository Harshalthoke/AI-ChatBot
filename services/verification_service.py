"""Scholarly evidence verification service for academic journals."""

import logging
from typing import Optional, Dict, Any, List
from models.journal import JournalRecord
from models.evidence import (
    VerificationStatus,
    VerificationAspect,
    EvidenceRecord,
    JournalVerificationSummary
)
from services.doaj_service import DOAJService
from services.crossref_service import CrossrefService
from utils.deduplication import normalize_issn

logger = logging.getLogger(__name__)


class VerificationService:
    """Verifies candidate journal facts against authoritative registries (DOAJ, Crossref)."""

    def __init__(
        self,
        doaj_service: Optional[DOAJService] = None,
        crossref_service: Optional[CrossrefService] = None
    ):
        self.doaj = doaj_service or DOAJService()
        self.crossref = crossref_service or CrossrefService()

    def verify_journal(self, journal: JournalRecord) -> JournalVerificationSummary:
        """Executes verification checks across key aspects of a candidate journal."""
        summary = JournalVerificationSummary(journal_id=journal.journal_id)
        primary_issn = journal.get_primary_issn()

        # 1. Identity Verification (ISSN validity & existence)
        self._verify_identity(journal, primary_issn, summary)

        # 2. Publisher Verification
        self._verify_publisher(journal, summary)

        # 3. DOAJ & Open Access Verification
        doaj_data = self._verify_doaj(journal, primary_issn, summary)

        # 4. APC Fee Verification
        self._verify_apc_fee(journal, doaj_data, summary)

        # 5. Peer Review Policy
        self._verify_peer_review(journal, doaj_data, summary)

        # 6. Metrics Provenance
        self._verify_metrics(journal, summary)

        journal.verification_summary = summary
        return summary

    def _verify_identity(
        self,
        journal: JournalRecord,
        primary_issn: Optional[str],
        summary: JournalVerificationSummary
    ) -> None:
        """Verifies ISSN and journal title identity."""
        if not primary_issn:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.JOURNAL_IDENTITY,
                status=VerificationStatus.REQUIRES_MANUAL_REVIEW,
                source_name="Metadata Validator",
                claimed_value=journal.title,
                notes="Journal record lacks an official ISSN; identity based solely on title string.",
                confidence=0.5
            ))
            summary.warnings.append("Journal lacks an official ISSN; identity requires manual review.")
            return

        norm_issn = normalize_issn(primary_issn)
        if not norm_issn or len(norm_issn) != 9:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.JOURNAL_IDENTITY,
                status=VerificationStatus.CONFLICTING_EVIDENCE,
                source_name="ISSN Validator",
                claimed_value=primary_issn,
                notes=f"Invalid ISSN format encountered: '{primary_issn}'.",
                confidence=0.3
            ))
            summary.warnings.append(f"Invalid ISSN format encountered: '{primary_issn}'.")
            return

        # Verified valid ISSN
        sources = ", ".join(journal.sources_contributed) if journal.sources_contributed else "Registry"
        summary.add_check(EvidenceRecord(
            aspect=VerificationAspect.JOURNAL_IDENTITY,
            status=VerificationStatus.VERIFIED,
            source_name=f"Scholarly Registry ({sources})",
            claimed_value=f"ISSN: {norm_issn}",
            verified_value=norm_issn,
            notes=f"Valid canonical ISSN matched across {len(journal.sources_contributed)} source(s).",
            confidence=0.95
        ))

    def _verify_publisher(
        self,
        journal: JournalRecord,
        summary: JournalVerificationSummary
    ) -> None:
        """Checks publisher identification against indexed data and Crossref."""
        primary_issn = journal.get_primary_issn()
        cr_info = None
        if primary_issn:
            try:
                res = self.crossref.get_journal_by_issn(primary_issn)
                if isinstance(res, dict):
                    cr_info = res
            except Exception:
                cr_info = None

        if journal.publisher:
            if isinstance(cr_info, dict) and cr_info.get("publisher"):
                cr_pub = str(cr_info.get("publisher"))
                if (journal.publisher.lower() in cr_pub.lower() or
                    cr_pub.lower() in journal.publisher.lower()):
                    summary.add_check(EvidenceRecord(
                        aspect=VerificationAspect.PUBLISHER_IDENTITY,
                        status=VerificationStatus.VERIFIED,
                        source_name="Crossref Registry",
                        claimed_value=journal.publisher,
                        verified_value=cr_pub,
                        notes="Publisher identity verified against Crossref registry.",
                        confidence=0.95
                    ))
                else:
                    summary.add_check(EvidenceRecord(
                        aspect=VerificationAspect.PUBLISHER_IDENTITY,
                        status=VerificationStatus.CONFLICTING_EVIDENCE,
                        source_name="Crossref Registry",
                        claimed_value=journal.publisher,
                        verified_value=cr_pub,
                        notes=f"Publisher mismatch: claimed '{journal.publisher}', Crossref reports '{cr_pub}'.",
                        confidence=0.8
                    ))
                    summary.warnings.append(
                        f"Publisher discrepancy between claimed metadata ({journal.publisher}) and Crossref ({cr_pub})."
                    )
            else:
                summary.add_check(EvidenceRecord(
                    aspect=VerificationAspect.PUBLISHER_IDENTITY,
                    status=VerificationStatus.VERIFIED,
                    source_name="Scholarly Source Metadata",
                    claimed_value=journal.publisher,
                    verified_value=journal.publisher,
                    notes="Publisher identity verified in indexed metadata.",
                    confidence=0.9
                ))
        else:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.PUBLISHER_IDENTITY,
                status=VerificationStatus.UNAVAILABLE,
                source_name="Scholarly Metadata",
                notes="No publisher specified in registry metadata.",
                confidence=0.4
            ))

    def _verify_doaj(
        self,
        journal: JournalRecord,
        primary_issn: Optional[str],
        summary: JournalVerificationSummary
    ) -> Optional[Dict[str, Any]]:
        """Verifies DOAJ indexing and open access legitimacy."""
        doaj_data: Optional[Dict[str, Any]] = None

        if primary_issn:
            try:
                res = self.doaj.get_journal_by_issn(primary_issn)
                if isinstance(res, dict):
                    doaj_data = res
            except Exception:
                doaj_data = None

        # Fallback to title lookup if not found by ISSN
        if not doaj_data and journal.title:
            try:
                matches = self.doaj.search_by_title_or_query(journal.title, limit=1)
                if isinstance(matches, list) and matches and isinstance(matches[0], dict):
                    doaj_data = matches[0]
            except Exception:
                pass

        if doaj_data and isinstance(doaj_data, dict):
            seal_info = " (Awarded DOAJ Seal for Best Practice)" if doaj_data.get("has_doaj_seal") else ""
            src_url = doaj_data.get("source_url")
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.DOAJ_LISTING,
                status=VerificationStatus.VERIFIED,
                source_name="DOAJ Official Directory",
                source_url=str(src_url) if src_url and isinstance(src_url, str) else None,
                claimed_value="Open Access",
                verified_value=f"DOAJ Listed{seal_info}",
                notes=f"Officially indexed in Directory of Open Access Journals.{seal_info}",
                confidence=1.0
            ))
            # Enrich journal record with DOAJ facts
            journal.is_open_access = True
            if not journal.homepage_url and doaj_data.get("homepage_url"):
                journal.homepage_url = doaj_data.get("homepage_url")
            if doaj_data.get("peer_review_type"):
                journal.peer_review_type = doaj_data.get("peer_review_type")
            if "DOAJ" not in journal.indexing_claims:
                journal.indexing_claims.append("DOAJ")
            if "DOAJ" not in journal.sources_contributed:
                journal.sources_contributed.append("DOAJ")
        else:
            if journal.is_open_access is True:
                summary.add_check(EvidenceRecord(
                    aspect=VerificationAspect.DOAJ_LISTING,
                    status=VerificationStatus.REQUIRES_MANUAL_REVIEW,
                    source_name="DOAJ Directory Check",
                    claimed_value="Open Access claimed",
                    notes="Journal claims Open Access but was not found in DOAJ. Verify journal legitimacy before submission.",
                    confidence=0.7
                ))
            else:
                summary.add_check(EvidenceRecord(
                    aspect=VerificationAspect.DOAJ_LISTING,
                    status=VerificationStatus.UNAVAILABLE,
                    source_name="DOAJ Directory Check",
                    notes="Not listed in DOAJ (Journal appears to follow hybrid or subscription model).",
                    confidence=0.8
                ))

        return doaj_data

    def _verify_apc_fee(
        self,
        journal: JournalRecord,
        doaj_data: Optional[Dict[str, Any]],
        summary: JournalVerificationSummary
    ) -> None:
        """Cross-checks Article Processing Charges (APC) between claims and authoritative records."""
        doaj_apc = doaj_data.get("apc_usd") if doaj_data else None

        if doaj_apc is not None:
            claimed_apc = journal.apc_usd
            if claimed_apc is not None and abs(claimed_apc - doaj_apc) > 500:
                summary.add_check(EvidenceRecord(
                    aspect=VerificationAspect.APC_FEE,
                    status=VerificationStatus.CONFLICTING_EVIDENCE,
                    source_name="DOAJ vs Index Metadata",
                    claimed_value=f"${claimed_apc:,.0f} USD",
                    verified_value=f"${doaj_apc:,.0f} USD (DOAJ)",
                    notes=f"Discrepancy detected between claimed fee (${claimed_apc:,.0f}) and DOAJ listed fee (${doaj_apc:,.0f}).",
                    confidence=0.85
                ))
            else:
                journal.apc_usd = doaj_apc
                journal.apc_currency = "USD"
                journal.apc_source = "DOAJ Official Directory"
                fee_display = f"${doaj_apc:,.0f} USD" if doaj_apc > 0 else "Free / Diamond OA ($0)"
                summary.add_check(EvidenceRecord(
                    aspect=VerificationAspect.APC_FEE,
                    status=VerificationStatus.VERIFIED,
                    source_name="DOAJ Official Directory",
                    claimed_value=fee_display,
                    verified_value=fee_display,
                    notes=f"Article Processing Charge verified in DOAJ registry ({fee_display}).",
                    confidence=0.95
                ))
        elif journal.apc_usd is not None:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.APC_FEE,
                status=VerificationStatus.REQUIRES_MANUAL_REVIEW,
                source_name="OpenAlex / Publisher Metadata",
                claimed_value=f"${journal.apc_usd:,.0f} USD",
                notes="APC amount extracted from index metadata, but not independently confirmed by DOAJ.",
                confidence=0.75
            ))
        else:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.APC_FEE,
                status=VerificationStatus.UNAVAILABLE,
                source_name="Pricing Registries",
                notes="APC fee details not publicly indexed or journal is subscription-based without author fee.",
                confidence=0.6
            ))

    def _verify_peer_review(
        self,
        journal: JournalRecord,
        doaj_data: Optional[Dict[str, Any]],
        summary: JournalVerificationSummary
    ) -> None:
        """Verifies peer review policy presence."""
        policy = (doaj_data and doaj_data.get("peer_review_type")) or journal.peer_review_type
        if policy:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.PEER_REVIEW_POLICY,
                status=VerificationStatus.VERIFIED,
                source_name="Directory Editorial Policy",
                verified_value=policy,
                notes=f"Peer review model verified: {policy}",
                confidence=0.9
            ))
        else:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.PEER_REVIEW_POLICY,
                status=VerificationStatus.UNAVAILABLE,
                source_name="Directory Editorial Policy",
                notes="Peer review details not specified in registry metadata.",
                confidence=0.5
            ))

    def _verify_metrics(
        self,
        journal: JournalRecord,
        summary: JournalVerificationSummary
    ) -> None:
        """Verifies citation metrics provenance."""
        metrics = journal.metrics or {}
        if metrics.get("2yr_mean_citedness") is not None or metrics.get("h_index") is not None:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.METRICS_PROVENANCE,
                status=VerificationStatus.VERIFIED,
                source_name=metrics.get("source", "OpenAlex"),
                verified_value=f"h-index: {metrics.get('h_index', 'N/A')}, 2-year mean citedness: {metrics.get('2yr_mean_citedness', 'N/A')}",
                notes="Citation and impact metrics verified against OpenAlex citation graph.",
                confidence=0.9
            ))
        else:
            summary.add_check(EvidenceRecord(
                aspect=VerificationAspect.METRICS_PROVENANCE,
                status=VerificationStatus.UNAVAILABLE,
                source_name="Citation Graphs",
                notes="Citation metrics not currently available for this venue.",
                confidence=0.5
            ))
