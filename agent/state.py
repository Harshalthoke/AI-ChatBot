"""State schema for Research Journal Finder LangGraph agent."""

from typing import TypedDict, List, Dict, Any, Optional
from models.research import ResearchProfile
from models.journal import JournalRecord, JournalRankingResult


class ResearchAgentState(TypedDict):
    """Execution state maintained across the research agent workflow."""
    profile: ResearchProfile
    queries: List[str]
    candidate_journals: Dict[str, JournalRecord]
    ranked_results: List[JournalRankingResult]
    current_iteration: int
    api_call_count: int
    no_progress_count: int
    status_logs: List[str]
    is_terminated: bool
    termination_reason: str
    research_summary: str
