from typing import Any, Optional, Dict
from .base import BaseMemory

class ExecutionMemory(BaseMemory):
    """
    Memory provider for ephemeral execution state (e.g., within a single graph run).
    """
    def __init__(self):
        self._storage: Dict[str, Any] = {}

    def load(self, key: str) -> Optional[Any]:
        return self._storage.get(key)

    def save(self, key: str, value: Any) -> None:
        self._storage[key] = value

    def clear(self, key: str) -> None:
        if key in self._storage:
            del self._storage[key]
