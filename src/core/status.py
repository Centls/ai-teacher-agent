from enum import Enum
from typing import TypedDict, Optional, Any, Dict

class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    REFUSED = "REFUSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"

class ReasonCode(str, Enum):
    PRD_VIOLATION = "PRD_VIOLATION"
    MISSING_INFO = "MISSING_INFO"
    MODEL_ERROR = "MODEL_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    NO_CAPABLE_AGENT = "NO_CAPABLE_AGENT"
    UNKNOWN = "UNKNOWN"
    NONE = "NONE"

class ExecutionEnvelope(TypedDict):
    """
    Standard return envelope for all Teacher nodes.
    """
    status: ExecutionStatus
    reason_code: Optional[ReasonCode]
    message: Optional[str] # Human readable message
    result: Optional[Any] # The actual payload (e.g. scratchpad update)
    diagnostics: Optional[Dict[str, Any]] # Debug info, violation details
    retryable: bool
