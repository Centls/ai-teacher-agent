from typing import Any, Optional
from .base import BaseMemory

class GlobalMemory(BaseMemory):
    """
    Memory provider for global/system-wide state.
    Currently a stub.
    """
    
    def load(self, key: str) -> Optional[Any]:
        # Placeholder for global config or shared knowledge base
        return None

    def save(self, key: str, value: Any) -> None:
        pass

    def clear(self, key: str) -> None:
        pass
