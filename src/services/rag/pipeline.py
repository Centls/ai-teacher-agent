import os
import logging
from typing import List, Optional
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader, TextLoader, CSVLoader, UnstructuredExcelLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

class RAGPipeline:
    """
    Standalone RAG Pipeline for AI Teacher Nexus.
    White-box reuse of concepts from Agentic-RAG-Ollama, but implemented with local infrastructure.
    """
    def __init__(self, vector_db_path: str = "./chroma_db", chunking_strategy: str = "auto"):
        """
        :param vector_db_path: Path for ChromaDB persistence
        :param chunking_strategy: 'auto', 'header', or 'character'.
        """
        self.vector_db_path = vector_db_path
        
        # Initialize Embeddings (Aliyun/OpenAI Compatible)
        api_key = settings.OPENAI_API_KEY
        if not api_key:
             # Fallback or error
             logger.warning("OPENAI_API_KEY not found in settings, using env var or placeholder")
             api_key = os.getenv("OPENAI_API_KEY", "sk-placeholder")

        self.embeddings = OpenAIEmbeddings(
            api_key=api_key,
            base_url=settings.OPENAI_API_BASE,
            model="text-embedding-v2", # Aliyun model
            check_embedding_ctx_length=False
        )
        
        self.vectorstore = Chroma(
            collection_name="financial_docs", # Keep consistent with what we used
            persist_directory=self.vector_db_path, 
            embedding_function=self.embeddings
        )
        self.chunking_strategy = chunking_strategy
        logger.info(f"Initialized RAGPipeline (Standalone, chunking_strategy={chunking_strategy})")

    def _get_text_splitter(self, docs, file_path: str):
        """
        Use MarkdownHeaderTextSplitter if markdown, else fallback to RecursiveCharacterTextSplitter.
        """
        ext = os.path.splitext(file_path)[-1].lower()
        if self.chunking_strategy == "header" or (self.chunking_strategy == "auto" and ext in ['.md', '.markdown']):
            try:
                return MarkdownHeaderTextSplitter(headers_to_split_on=["#", "##", "###"], strip_headers=False)
            except Exception as e:
                logger.warning(f"Header splitter failed: {e}, falling back to character splitter.")
        # Fallback
        return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

    def load_document(self, file_path: str) -> List[Document]:
        ext = os.path.splitext(file_path)[-1].lower()
        if ext == '.pdf':
            loader = PyPDFLoader(file_path)
        elif ext == '.docx':
            loader = UnstructuredWordDocumentLoader(file_path)
        elif ext == '.txt':
            loader = TextLoader(file_path, encoding="utf-8")
        elif ext == '.csv':
            loader = CSVLoader(file_path)
        elif ext == '.xlsx':
            loader = UnstructuredExcelLoader(file_path)
        elif ext in ['.md', '.markdown']:
             # Use TextLoader for markdown to keep raw text for header splitter
             loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
        docs = loader.load()
        return docs

    def ingest(self, file_path: str, metadata: dict = None):
        """
        Ingests a file using adaptive chunking.
        """
        docs = self.load_document(file_path)
        splitter = self._get_text_splitter(docs, file_path)
        
        # MarkdownHeaderTextSplitter expects string, not documents
        if isinstance(splitter, MarkdownHeaderTextSplitter):
            text = "\n\n".join([d.page_content for d in docs])
            splits = splitter.split_text(text)
        else:
            splits = splitter.split_documents(docs)
            
        # Attach file-level metadata
        for doc in splits:
            doc.metadata = doc.metadata or {}
            if metadata:
                doc.metadata.update(metadata)
            doc.metadata['source_file'] = file_path
            
        self.vectorstore.add_documents(splits)
        logger.info(f"Ingested {len(splits)} chunks from {file_path}")

    def ingest_text(self, text: str, metadata: dict = None):
        """
        Ingest raw text.
        """
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        doc = Document(page_content=text, metadata=metadata or {})
        splits = splitter.split_documents([doc])
        self.vectorstore.add_documents(splits)
        logger.info(f"Ingested {len(splits)} chunks from raw text")

    def retrieve(self, query: str, k: int = 4, keywords: Optional[list] = None, metadata_filter: Optional[dict] = None) -> List[Document]:
        """
        Hybrid retrieval: Vector Search + BM25 Re-ranking (if keywords provided).
        """
        # 1. Vector Search (Fetch more candidates for re-ranking)
        fetch_k = k * 5 if keywords else k
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": fetch_k, "filter": metadata_filter} if metadata_filter else {"k": fetch_k})
        results = retriever.invoke(query)
        
        # 2. BM25 Re-ranking (if keywords provided)
        if keywords:
            try:
                from rank_bm25 import BM25Plus
                import re
                
                def extract_headings_with_content(text):
                    chunks = []
                    sections = text.split('\n\n')
                    i = 0
                    while i < len(sections):
                        section = sections[i].strip()
                        pattern = r"^#+\s+"
                        if re.match(pattern, section):
                            heading = section
                            if i + 1 < len(sections):
                                next_content = sections[i+1].strip()
                                chunk = f"{heading}\n\n{next_content}"
                                i += 2
                            else:
                                chunk = heading
                                i += 1
                            chunks.append(chunk)
                        else:
                            i += 1
                    return chunks

                logger.info(f"Re-ranking {len(results)} docs with keywords: {keywords}")
                
                query_tokens = " ".join(keywords).lower().split(" ")
                doc_chunks = []
                for doc in results:
                    chunks = extract_headings_with_content(doc.page_content)
                    combined = " ".join(chunks) if chunks else doc.page_content
                    doc_chunks.append(combined.lower().split(' '))

                bm25 = BM25Plus(doc_chunks)
                doc_scores = bm25.get_scores(query_tokens)
                
                # Sort by score
                ranked_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)
                results = [results[i] for i in ranked_indices[:k]]
                
            except ImportError:
                logger.warning("rank_bm25 not installed, skipping re-ranking.")
                results = results[:k]
            except Exception as e:
                logger.error(f"BM25 re-ranking failed: {e}")
                results = results[:k]
            
        logger.info(f"Hybrid retrieval for query '{query}': {len(results)} docs")
        return results

    def delete_document(self, source_file: str):
        """
        Delete all chunks associated with a specific source file.
        """
        try:
            # 1. Find IDs to delete
            # Note: LangChain's Chroma wrapper uses 'where' for metadata filtering in get()
            data = self.vectorstore.get(where={"source_file": source_file})
            ids_to_delete = data['ids']
            
            if not ids_to_delete:
                logger.warning(f"No documents found for source_file: {source_file}")
                return False
                
            # 2. Delete by IDs
            self.vectorstore.delete(ids=ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} chunks for source_file: {source_file}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {source_file}: {e}")
            return False
