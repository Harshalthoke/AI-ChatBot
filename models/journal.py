"""Canonical journal record and ranking result data models."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from models.evidence import VerificationStatus, JournalVerificationSummary


class RepresentativePublication(BaseModel):
    """A paper published in the journal that matches the query."""
    title: str
    doi: Optional[str] = None
    publication_year: Optional[int] = None
    cited_by_count: Optional[int] = None
    source_url: Optional[str] = None
    similarity_score: Optional[float] = None


class JournalRecord(BaseModel):
    """Canonical, deduplicated academic journal record."""
    journal_id: str  # Unique canonical identifier (normalized ISSN-L, ISSN, or slug)
    title: str
    alternate_titles: List[str] = Field(default_factory=list)
    issn_print: Optional[str] = None
    issn_electronic: Optional[str] = None
    issn_linking: Optional[str] = None
    publisher: Optional[str] = None
    homepage_url: Optional[str] = None
    aims_and_scope: Optional[str] = None
    subject_areas: List[str] = Field(default_factory=list)
    
    # Open access & fees
    is_open_access: Optional[bool] = None
    apc_usd: Optional[float] = None
    apc_currency: Optional[str] = None
    apc_source: Optional[str] = None
    
    # Peer review & frequency
    peer_review_type: Optional[str] = None
    publication_frequency: Optional[str] = None
    
    # Indexing & metrics
    indexing_claims: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)  # e.g., {"h_index": 45, "2yr_mean_citedness": 3.8, "source": "OpenAlex"}
    
    # Evidence & provenance
    representative_publications: List[RepresentativePublication] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)
    retrieval_timestamps: Dict[str, str] = Field(default_factory=dict)
    sources_contributed: List[str] = Field(default_factory=list)  # e.g., ["OpenAlex", "Crossref", "DOAJ"]
    
    # Metadata completeness & verification
    verification_summary: Optional[JournalVerificationSummary] = None
    missing_fields: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.7, ge=0.0, le=1.0)

    def get_primary_issn(self) -> Optional[str]:
        return self.issn_linking or self.issn_electronic or self.issn_print

    def compute_missing_fields(self) -> List[str]:
        missing = []
        if not self.issn_print and not self.issn_electronic:
            missing.append("ISSN")
        if not self.publisher:
            missing.append("Publisher")
        if not self.homepage_url:
            missing.append("Official Homepage")
        if not self.aims_and_scope:
            missing.append("Aims & Scope")
        if self.is_open_access is None:
            missing.append("Open Access Status")
        if self.apc_usd is None and self.is_open_access is True:
            missing.append("APC Fee details")
        if not self.peer_review_type:
            missing.append("Peer Review Policy")
        self.missing_fields = missing
        return missing

    def evidence_completeness_ratio(self) -> float:
        """Ratio of available metadata fields out of tracked key fields."""
        tracked = [
            bool(self.issn_print or self.issn_electronic),
            bool(self.publisher),
            bool(self.homepage_url),
            bool(self.aims_and_scope),
            self.is_open_access is not None,
            bool(self.peer_review_type),
            len(self.subject_areas) > 0,
            len(self.representative_publications) > 0
        ]
        return sum(1 for t in tracked if t) / len(tracked)


class JournalRankingResult(BaseModel):
    """Detailed multi-criteria ranking output for a candidate journal."""
    journal: JournalRecord
    rank: int = 1
    
    # Component scores - normalized between 0.0 and 1.0
    research_relevance_score: float = Field(..., ge=0.0, le=1.0, description="Overall topic, semantic, and domain alignment")
    publication_suitability_score: float = Field(..., ge=0.0, le=1.0, description="User constraints alignment (OA preference, budget, indexing)")
    evidence_completeness_score: float = Field(..., ge=0.0, le=1.0, description="Completeness of verifiable facts")
    
    # Detailed sub-scores
    semantic_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    topic_concept_overlap: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_match: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Verification and provenance
    verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Grounded explanation
    recommendation_explanation: str = ""
    mismatch_warnings: List[str] = Field(default_factory=list)
    confidence_notes: str = ""

    def __init__(self, **data):
        if "suitability_explanation" in data and "recommendation_explanation" not in data:
            data["recommendation_explanation"] = data.pop("suitability_explanation")
        super().__init__(**data)

    @property
    def suitability_explanation(self) -> str:
        return self.recommendation_explanation
