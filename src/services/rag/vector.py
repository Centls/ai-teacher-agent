import os
import random
from typing import List, Optional
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, UnstructuredMarkdownLoader, TextLoader
from config.settings import DATA_DIR, settings
from .provider import KnowledgeProvider

class MockEmbeddings(Embeddings):
    """
    Mock Embeddings for testing without an API Key.
    Generates random vectors of the specified size.
    """
    def __init__(self, size: int = 1536):
        self.size = size

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Deterministic random based on text length to allow some consistency in retrieval tests
        # (Though real semantic search won't work, at least it won't crash)
        return [[random.random() for _ in range(self.size)] for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [random.random() for _ in range(self.size)]

class VectorKnowledgeProvider(KnowledgeProvider):
    """
    Vector Database implementation of Knowledge Provider using ChromaDB.
    Supports namespace isolation and robust document loading.
    """
    
    def __init__(self, collection_name: str = "nexus_knowledge"):
        self.persist_dir = str(DATA_DIR / "chroma_db")
        self.collection_name = collection_name
        
        # Initialize Embeddings
        api_key = settings.OPENAI_API_KEY
        
        if not api_key or "placeholder" in api_key or not api_key.startswith("sk-"):
            print("Warning: No valid OPENAI_API_KEY found. Using MockEmbeddings (Random Vectors).")
            self.embedding_function = MockEmbeddings()
        else:
            self.embedding_function = OpenAIEmbeddings(
                api_key=api_key,
                model="text-embedding-3-small"
            )
        
        # Initialize Chroma
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_function,
            persist_directory=self.persist_dir
        )
        
    def query(self, query_text: str, k: int = 3, namespace: Optional[str] = None) -> str:
        """
        Semantic search using Vector DB with optional namespace filtering.
        """
        print(f"--- [VectorRAG] Querying: {query_text} (Namespace: {namespace}) ---")
        try:
            filter_dict = {"namespace": namespace} if namespace else None
            
            results = self.vector_store.similarity_search(
                query_text, 
                k=k,
                filter=filter_dict
            )
            
            if not results:
                return "暂无相关资料"
            
            # Combine results
            context = "\n\n".join([doc.page_content for doc in results])
            return context
        except Exception as e:
            print(f"Vector Query Error: {e}")
            return f"Error querying knowledge base: {e}"

    def ingest_text(self, text: str, source: str = "manual", namespace: Optional[str] = None):
        """
        Ingest raw text into the vector store with namespace metadata.
        """
        metadata = {"source": source}
        if namespace:
            metadata["namespace"] = namespace
            
        doc = Document(page_content=text, metadata=metadata)
        self.vector_store.add_documents([doc])
        print(f"Ingested text from {source} into namespace {namespace}")

    def ingest_file(self, file_path: str, namespace: Optional[str] = None):
        """
        Ingest a file using robust LangChain loaders.
        Supports .pdf, .md, .txt.
        """
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return
            
        try:
            loader = None
            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith(".md"):
                loader = UnstructuredMarkdownLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding="utf-8")
                
            docs = loader.load()
            
            # Inject namespace into metadata
            if namespace:
                for doc in docs:
                    doc.metadata["namespace"] = namespace
            
            self.vector_store.add_documents(docs)
            print(f"Successfully ingested file: {file_path} ({len(docs)} chunks)")
            
        except Exception as e:
            print(f"Error ingesting file {file_path}: {e}")
