from typing import TypedDict, Optional
from src.core.state_mgr import NexusState

class SupportState(NexusState):
    """
    Support specific state extensions.
    """
    issue_category: Optional[str]
    solution: Optional[str]
    confidence_score: Optional[float]
    boundary_check_result: Optional[str] # PASS / FAIL
