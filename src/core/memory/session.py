from typing import Any, Optional
from .base import BaseMemory
from src.core.lifecycle import SessionManager

class SessionMemory(BaseMemory):
    """
    Memory provider for session-scoped state.
    Wraps SessionManager to provide a standard interface.
    """
    
    def load(self, key: str) -> Optional[Any]:
        """Load session state by session_id."""
        return SessionManager.get_session(key)

    def save(self, key: str, value: Any) -> None:
        """
        Save session state. 
        Note: SessionManager currently holds state in memory, so explicit save might be redundant
        if we are just modifying the dict in place, but this ensures interface compliance.
        """
        # In a real DB implementation, this would persist to DB.
        # For now, SessionManager._sessions[key] = value is handled by reference usually,
        # but let's be explicit if we want to support full replacement.
        if key in SessionManager._sessions:
             SessionManager._sessions[key] = value

    def clear(self, key: str) -> None:
        """Close/Clear session."""
        SessionManager.close_session(key)
