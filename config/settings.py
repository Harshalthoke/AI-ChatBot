"""Configuration settings for Research Journal Finder AI."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")


class SearchThresholds(BaseModel):
    """Configurable thresholds for research and agent search termination."""
    min_candidates: int = Field(default=8, ge=1, le=50, description="Minimum target candidate journals before stopping early")
    min_relevance_score: float = Field(default=0.45, ge=0.0, le=1.0, description="Minimum research relevance threshold")
    min_evidence_completeness: float = Field(default=0.60, ge=0.0, le=1.0, description="Desired evidence completeness score (0-1)")
    max_consecutive_no_progress: int = Field(default=2, ge=1, le=5, description="Stop after N consecutive loops without new journals")
    max_iterations: int = Field(default=4, ge=1, le=10, description="Maximum research refinement iterations")
    max_api_calls: int = Field(default=40, ge=5, le=150, description="Hard cap on external API requests per search session")
    max_execution_time_seconds: float = Field(default=180.0, ge=10.0, le=600.0, description="Timeout budget for complete search run")


class RankingWeights(BaseModel):
    """Configurable weights for multi-criteria journal ranking."""
    weight_semantic_similarity: float = Field(default=0.40, ge=0.0, le=1.0)
    weight_topic_concept_match: float = Field(default=0.25, ge=0.0, le=1.0)
    weight_domain_match: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_publication_suitability: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_evidence_completeness: float = Field(default=0.10, ge=0.0, le=1.0)


class AppSettings(BaseModel):
    """Main application settings loaded from environment and defaults."""
    app_name: str = "Research Journal Finder AI"
    version: str = "1.0.0"
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    reports_dir: Path = BASE_DIR / "reports"
    db_path: Path = BASE_DIR / "data" / "journal_finder.db"

    # API credentials & endpoints
    openalex_email: str = Field(
        default_factory=lambda: os.getenv("OPENALEX_EMAIL", "researcher@example.com")
    )
    crossref_email: str = Field(
        default_factory=lambda: os.getenv("CROSSREF_EMAIL", "researcher@example.com")
    )
    
    # Optional LLM settings
    llm_provider: str = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "fallback")  # "gemini", "openai", "ollama", "fallback"
    )
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    openai_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    gemini_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    )
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2")
    )

    # API Request settings
    request_timeout_seconds: float = 12.0
    max_request_retries: int = 3
    cache_ttl_hours: int = 48

    # Sub-configs
    thresholds: SearchThresholds = Field(default_factory=SearchThresholds)
    ranking_weights: RankingWeights = Field(default_factory=RankingWeights)


# Global settings singleton
settings = AppSettings()

# Ensure required directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.reports_dir.mkdir(parents=True, exist_ok=True)
