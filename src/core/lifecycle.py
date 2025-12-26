import uuid
from typing import Dict, Optional
from .state_mgr import NexusState, StateMeta

class SessionManager:
    _sessions: Dict[str, NexusState] = {}

    @classmethod
    def create_session(cls, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        initial_state: NexusState = {
            "messages": [],
            "user_context": {"user_id": user_id},
            "next_node": None,
            "status": "SUCCESS",
            "error": None,
            "meta": {"version": "1.0", "session_id": session_id, "user_id": user_id},
            "scratchpad": {}
        }
        cls._sessions[session_id] = initial_state
        print(f"Session created: {session_id}")
        return session_id

    @classmethod
    def get_session(cls, session_id: str) -> Optional[NexusState]:
        return cls._sessions.get(session_id)

    @classmethod
    def close_session(cls, session_id: str):
        if session_id in cls._sessions:
            del cls._sessions[session_id]
            print(f"Session closed: {session_id}")

    @classmethod
    def get_thread_id(cls, session_id: str) -> str:
        """
        Returns the thread_id associated with the session.
        Currently maps 1:1 with session_id.
        """
        return session_id

LifecycleManager = SessionManager
