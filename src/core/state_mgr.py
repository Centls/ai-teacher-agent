from typing import TypedDict, Annotated, List, Dict, Any, Optional, Union
import operator
from .status import ExecutionEnvelope


def merge_dicts(a: Dict, b: Dict) -> Dict:
    return {**a, **b}

class Message(TypedDict):
    role: str
    content: str
    name: Optional[str]
    timestamp: Optional[str]

class StateMeta(TypedDict):
    version: str
    session_id: str
    user_id: str

class NexusState(TypedDict):
    """
    Global State for the Nexus System.
    Follows backward compatibility rules: new fields must be Optional.
    """
    # Messages history
    messages: Annotated[List[Message], operator.add]
    
    # Context
    user_context: Dict[str, Any]
    
    # Routing
    next_node: Optional[str]
    
    # Status
    status: str # SUCCESS, REFUSAL, FALLBACK
    error: Optional[str]
    prd_compliance: Optional[str] # PASS / FAIL
    
    # Metadata
    meta: StateMeta
    
    # PRD Context (Global Read-Only Constraints)
    prd_context: Annotated[Dict[str, Any], merge_dicts]
    
    # Scratchpad for teachers (optional)
    scratchpad: Annotated[Dict[str, Any], merge_dicts]

    # Execution Result (Unified Failure Governance)
    execution_result: Optional[ExecutionEnvelope]

    # Self-Reflection & Correction
    reflection_score: Optional[float]
    reflection_issues: Optional[List[str]]
    correction_action: Optional[str] # ACCEPT, RETRY, SWITCH_TEACHER, HITL
    retry_count: Optional[int]
    last_teacher: Optional[str]

    # Supervisor 2.0 (Multi-Agent Orchestration)
    execution_plan: Optional[List[Dict[str, Any]]] # [{"agent": "researcher", "task": "..."}]
    results_buffer: Annotated[Dict[str, Any], merge_dicts] # {"researcher": {...}}
