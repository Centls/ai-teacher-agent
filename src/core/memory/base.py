from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseMemory(ABC):
    """
    Abstract base class for all memory providers.
    """
    
    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """Load data from memory."""
        pass

    @abstractmethod
    def save(self, key: str, value: Any) -> None:
        """Save data to memory."""
        pass

    @abstractmethod
    def clear(self, key: str) -> None:
        """Clear data from memory."""
        pass
