from abc import ABC, abstractmethod

class KnowledgeProvider(ABC):
    """
    Abstract base class for Knowledge Providers (RAG).
    """
    
    @abstractmethod
    def query(self, query_text: str) -> str:
        """
        Query the knowledge base.
        
        Args:
            query_text: The search query.
            
        Returns:
            str: The retrieved knowledge content.
        """
        pass
