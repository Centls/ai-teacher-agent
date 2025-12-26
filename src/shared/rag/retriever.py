from typing import List, Dict, Any

class SearchResult(Dict):
    content: str
    media_type: str # text, image, video
    metadata: Dict

class RAGRetriever:
    def __init__(self, namespace: str):
        self.namespace = namespace

    def search(self, query: str, top_k: int = 3) -> List[SearchResult]:
        """
        Mock RAG search.
        """
        print(f"Searching in namespace: {self.namespace} for '{query}'")
        return [
            SearchResult(content=f"Knowledge about {query} in {self.namespace}", media_type="text", metadata={})
        ]
