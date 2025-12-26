from typing import TypedDict, Optional, List, Dict, Any
from src.core.state_mgr import NexusState

class ResearcherState(NexusState):
    """
    State for the Researcher Agent.
    """
    research_plan: Optional[List[str]] # List of search queries
    search_results: Optional[List[Dict[str, Any]]] # Results from search tool
    summary: Optional[str] # Final summary
    research_loop_count: Optional[int] # Safety limit
