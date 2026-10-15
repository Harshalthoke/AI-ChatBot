"""Research paper submission and analysis data models."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class AccessPreference(str, Enum):
    ANY = "any"
    OPEN_ACCESS = "open_access"
    HYBRID_OR_SUBSCRIPTION = "subscription"


class PublicationType(str, Enum):
    ANY = "any"
    ORIGINAL_ARTICLE = "original_article"
    REVIEW_ARTICLE = "review_article"
    SHORT_COMMUNICATION = "short_communication"
    METHODOLOGY = "methodology"
    CASE_STUDY = "case_study"


class ResearchInputSubmission(BaseModel):
    """Raw user input before analysis."""
    title: str = Field(..., min_length=5, description="Research title")
    abstract: str = Field(..., min_length=20, description="Full abstract text")
    keywords: List[str] = Field(default_factory=list, description="Author provided keywords")
    domain: str = Field(default="General Science", description="Target scientific discipline")
    preferred_access: AccessPreference = Field(default=AccessPreference.ANY)
    max_apc_usd: Optional[float] = Field(default=None, ge=0.0, description="Maximum acceptable APC fee in USD")
    indexing_preferences: List[str] = Field(
        default_factory=lambda: ["DOAJ", "Scopus", "Web of Science"]
    )
    subject_categories: List[str] = Field(default_factory=list)
    publication_type: PublicationType = Field(default=PublicationType.ANY)

    @field_validator("title")
    @classmethod
    def validate_title_content(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned.split()) < 2:
            raise ValueError("Research title must contain at least 2 words.")
        return cleaned

    @field_validator("abstract")
    @classmethod
    def validate_abstract_content(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned.split()) < 10:
            raise ValueError("Abstract must contain at least 10 words to enable semantic matching.")
        return cleaned


class ResearchProfile(BaseModel):
    """Structured research profile generated from raw input or PDF."""
    title: str
    abstract: str
    keywords: List[str] = Field(default_factory=list)
    domain: str = "General Science"
    methodology: Optional[str] = None
    key_concepts: List[str] = Field(default_factory=list)
    preferred_access: AccessPreference = AccessPreference.ANY
    max_apc_usd: Optional[float] = None
    indexing_preferences: List[str] = Field(default_factory=list)
    subject_categories: List[str] = Field(default_factory=list)
    publication_type: PublicationType = PublicationType.ANY
    
    # Analysis metadata
    missing_information_notes: List[str] = Field(default_factory=list)
    generated_search_queries: List[str] = Field(default_factory=list)
    extraction_source: str = "manual_entry"  # "manual_entry" or "pdf_upload"
    word_count: int = 0
    validation_warnings: List[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Research title cannot be empty.")
        return cleaned

    @field_validator("abstract")
    @classmethod
    def validate_abstract_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Abstract cannot be empty.")
        return cleaned

    def __init__(self, **data):
        if "access_preference" in data and "preferred_access" not in data:
            data["preferred_access"] = data.pop("access_preference")
        super().__init__(**data)

    @property
    def access_preference(self) -> AccessPreference:
        return self.preferred_access

    def full_text_representation(self) -> str:
        """Consolidated string used for embedding and semantic comparisons."""
        parts = [f"Title: {self.title}", f"Abstract: {self.abstract}"]
        if self.keywords:
            parts.append(f"Keywords: {', '.join(self.keywords)}")
        if self.domain:
            parts.append(f"Domain: {self.domain}")
        if self.key_concepts:
            parts.append(f"Key Concepts: {', '.join(self.key_concepts)}")
        if self.methodology:
            parts.append(f"Methodology: {self.methodology}")
        return "\n".join(parts)
