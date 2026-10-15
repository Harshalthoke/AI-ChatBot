"""Evidence models and verification status representations."""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Explicit verification states required by research verification policy."""
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNAVAILABLE = "UNAVAILABLE"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"


class VerificationAspect(str, Enum):
    """Specific journal attributes subject to verification."""
    JOURNAL_IDENTITY = "journal_identity"
    PUBLISHER_IDENTITY = "publisher_identity"
    OFFICIAL_WEBSITE = "official_website"
    DOAJ_LISTING = "doaj_listing"
    SCOPUS_INDEXING = "scopus_indexing"
    WEB_OF_SCIENCE_INDEXING = "web_of_science_indexing"
    APC_FEE = "apc_fee"
    PEER_REVIEW_POLICY = "peer_review_policy"
    METRICS_PROVENANCE = "metrics_provenance"


class EvidenceRecord(BaseModel):
    """An individual piece of verifiable evidence obtained from a scholarly source."""
    aspect: VerificationAspect
    status: VerificationStatus
    source_name: str  # e.g., "DOAJ API", "OpenAlex Sources", "Crossref API"
    source_url: Optional[str] = None
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    claimed_value: Optional[str] = None
    verified_value: Optional[str] = None
    notes: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class JournalVerificationSummary(BaseModel):
    """Summary of all verification checks performed on a candidate journal."""
    journal_id: str
    overall_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    checks: Dict[str, EvidenceRecord] = Field(default_factory=dict)
    verified_count: int = 0
    conflicting_count: int = 0
    unavailable_count: int = 0
    requires_review_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    last_verified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_check(self, check: EvidenceRecord) -> None:
        self.checks[check.aspect.value] = check
        self._recompute_stats()

    def _recompute_stats(self) -> None:
        self.verified_count = sum(1 for c in self.checks.values() if c.status == VerificationStatus.VERIFIED)
        self.conflicting_count = sum(1 for c in self.checks.values() if c.status == VerificationStatus.CONFLICTING_EVIDENCE)
        self.unavailable_count = sum(1 for c in self.checks.values() if c.status == VerificationStatus.UNAVAILABLE)
        self.requires_review_count = sum(1 for c in self.checks.values() if c.status == VerificationStatus.REQUIRES_MANUAL_REVIEW)

        if self.conflicting_count > 0:
            self.overall_status = VerificationStatus.CONFLICTING_EVIDENCE
        elif self.requires_review_count > 0:
            self.overall_status = VerificationStatus.REQUIRES_MANUAL_REVIEW
        elif self.verified_count >= 2:
            self.overall_status = VerificationStatus.VERIFIED
        elif self.unavailable_count == len(self.checks) and len(self.checks) > 0:
            self.overall_status = VerificationStatus.UNAVAILABLE
        else:
            self.overall_status = VerificationStatus.NOT_VERIFIED

    @property
    def is_doaj_listed(self) -> bool:
        """Helper to determine if journal is confirmed in DOAJ registry."""
        check = self.checks.get(VerificationAspect.DOAJ_LISTING.value)
        return check is not None and check.status == VerificationStatus.VERIFIED

