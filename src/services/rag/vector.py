import os
from typing import Optional
from config.settings import DATA_DIR
from .provider import KnowledgeProvider
from .pipeline import RAGPipeline

class VectorKnowledgeProvider(KnowledgeProvider):
    """
    Vector Database implementation using Adapted RAGPipeline (Chroma).
    """
    
    def __init__(self, collection_name: str = "nexus_knowledge"):
        # RAGPipeline manages its own vector store path, but we can pass one.
        # We'll use a subdir in DATA_DIR
        self.persist_dir = str(DATA_DIR / "chroma_db")
        self.pipeline = RAGPipeline(vector_db_path=self.persist_dir)
        self.collection_name = collection_name
        
    def query(self, query_text: str, k: int = 3, namespace: Optional[str] = None) -> str:
        print(f"--- [ChromaRAG] Querying: {query_text} (Namespace: {namespace}) ---")
        try:
            metadata_filter = {"namespace": namespace} if namespace else None
            results = self.pipeline.retrieve(query_text, k=k, metadata_filter=metadata_filter)
            
            if not results:
                return "暂无相关资料"
            
            return "\n\n".join([doc.page_content for doc in results])
            
        except Exception as e:
            print(f"Vector Query Error: {e}")
            return f"Error querying knowledge base: {e}"

    def ingest_text(self, text: str, source: str = "manual", namespace: Optional[str] = None):
        metadata = {"source": source}
        if namespace:
            metadata["namespace"] = namespace
        self.pipeline.ingest_text(text, metadata=metadata)
        print(f"Ingested text from {source}")

    def ingest_file(self, file_path: str, namespace: Optional[str] = None):
        metadata = {}
        if namespace:
            metadata["namespace"] = namespace
        self.pipeline.ingest(file_path, metadata=metadata)
        print(f"Successfully ingested file: {file_path}")
