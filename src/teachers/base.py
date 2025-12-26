from abc import ABC, abstractmethod
from langgraph.graph import StateGraph
from src.core.capability import CapabilitySchema

class BaseTeacher(ABC):
    @abstractmethod
    def compile_graph(self) -> StateGraph:
        """
        Returns the compiled graph for this teacher.
        """
        pass

    @abstractmethod
    def capability(self) -> "CapabilitySchema":
        """
        Returns the capability declaration for this teacher.
        """
        pass
