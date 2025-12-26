import os
import sqlite3
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import DATA_DIR, settings
from .provider import KnowledgeProvider
from .vector import MockEmbeddings

class ChromaKnowledgeProvider(KnowledgeProvider):
    """
    Production-grade Knowledge Provider using ChromaDB for vectors 
    and SQLite for document metadata.
    """
    
    def __init__(self, collection_name: str = "nexus_knowledge"):
        self.persist_dir = str(DATA_DIR / "chroma_db")
        self.metadata_db_path = str(DATA_DIR / "rag_metadata.db")
        self.collection_name = collection_name
        
        # Ensure data directory exists
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # Initialize SQLite Metadata DB
        self._init_metadata_db()
        
        # Initialize Embeddings
        api_key = settings.OPENAI_API_KEY
        if not api_key or "placeholder" in api_key or not api_key.startswith("sk-"):
            print("Warning: No valid OPENAI_API_KEY found. Using MockEmbeddings.")
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
        
        # Initialize Text Splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    def _init_metadata_db(self):
        """Initialize SQLite database for document metadata."""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT,
                source_path TEXT,
                upload_date TEXT,
                status TEXT,
                chunk_count INTEGER
            )
        ''')
        conn.commit()
        conn.close()

    def ingest_document(self, file_path: str) -> str:
        """
        Ingest a document: Read -> Split -> Embed -> Store.
        Returns the Document ID.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # 1. Read Content
        # Simple text reading for now. Future: Support PDF/Docx via Unstructured
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            # Fallback for non-utf8? Or just fail for now.
            raise ValueError(f"Could not read file {file_path} as UTF-8.")
            
        # 2. Split Content
        chunks = self.text_splitter.create_documents([text], metadatas=[{"source": str(path)}])
        
        # 3. Generate Doc ID and Metadata
        doc_id = str(uuid.uuid4())
        upload_date = datetime.now().isoformat()
        
        # Add doc_id to chunk metadata
        for chunk in chunks:
            chunk.metadata["doc_id"] = doc_id
            chunk.metadata["filename"] = path.name
            
        # 4. Store in Chroma
        self.vector_store.add_documents(chunks)
        
        # 5. Store Metadata in SQLite
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents (id, filename, source_path, upload_date, status, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (doc_id, path.name, str(path), upload_date, "active", len(chunks)))
        conn.commit()
        conn.close()
        
        print(f"Ingested document {path.name} (ID: {doc_id}) with {len(chunks)} chunks.")
        return doc_id

    def query(self, query_text: str, k: int = 3) -> str:
        """
        Semantic search with metadata enrichment.
        """
        print(f"--- [ChromaService] Querying: {query_text} ---")
        try:
            results = self.vector_store.similarity_search(query_text, k=k)
            if not results:
                return "暂无相关资料"
            
            # Format results with source info
            formatted_results = []
            for doc in results:
                source = doc.metadata.get("filename", "Unknown Source")
                content = doc.page_content
                formatted_results.append(f"[Source: {source}]\n{content}")
            
            return "\n\n".join(formatted_results)
        except Exception as e:
            print(f"Chroma Query Error: {e}")
            return f"Error querying knowledge base: {e}"

    def get_documents(self) -> List[Dict]:
        """List all ingested documents from SQLite."""
        conn = sqlite3.connect(self.metadata_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents ORDER BY upload_date DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
