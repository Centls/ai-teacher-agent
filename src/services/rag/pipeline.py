import os
import logging
from typing import List, Optional
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader, TextLoader, CSVLoader, UnstructuredExcelLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from config.settings import settings, MODELS_DIR

# Configure logging
logger = logging.getLogger(__name__)


def _get_reranker_device() -> str:
    """
    自动检测最优计算设备（CPU/GPU/MPS）

    依赖：torch（由 sentence-transformers 自动安装）
    返回：'cuda' | 'mps' | 'cpu'
    """
    import torch

    device_config = settings.RERANKER_DEVICE.lower()

    if device_config != "auto":
        return device_config

    # 自动检测
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"🚀 Reranker: 检测到 GPU - {device_name}")
        return "cuda"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        logger.info("🍎 Reranker: 检测到 Apple MPS")
        return "mps"
    else:
        logger.info("💻 Reranker: 使用 CPU")
        return "cpu"

class RAGPipeline:
    """
    Standalone RAG Pipeline for AI Teacher Nexus.
    White-box reuse of concepts from Agentic-RAG-Ollama, but implemented with local infrastructure.
    """
    def __init__(self, vector_db_path: str = "./data/chroma_db", chunking_strategy: str = "auto"):
        """
        :param vector_db_path: Path for ChromaDB persistence
        :param chunking_strategy: 'auto', 'header', or 'character'.
        """
        self.vector_db_path = vector_db_path
        
        # Initialize Embeddings (Aliyun/OpenAI Compatible)
        # Initialize Embeddings based on configuration
        if settings.EMBEDDING_PROVIDER == "local":
            from langchain_huggingface import HuggingFaceEmbeddings

            # HF_HOME is already set in config/settings.py, no need to set cache_folder
            # Try offline first, fallback to online download if model not found
            try:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={"local_files_only": True}
                )
                logger.info(f"Using Local Embeddings: {settings.EMBEDDING_MODEL} (offline mode)")
            except Exception as e:
                logger.warning(f"Model not found locally, downloading: {settings.EMBEDDING_MODEL}")
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL
                )
                logger.info(f"Using Local Embeddings: {settings.EMBEDDING_MODEL} (downloaded)")
        else:
            # Default to OpenAI/Aliyun
            self.embeddings = OpenAIEmbeddings(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
                model=settings.EMBEDDING_MODEL,
                check_embedding_ctx_length=False
            )
            logger.info(f"Using OpenAI Embeddings: {settings.EMBEDDING_MODEL}")
        
        self.vectorstore = Chroma(
            collection_name="financial_docs", # Keep consistent with what we used
            persist_directory=self.vector_db_path, 
            embedding_function=self.embeddings
        )
        self.chunking_strategy = chunking_strategy
        logger.info(f"Initialized RAGPipeline (Standalone, chunking_strategy={chunking_strategy})")

        # Reranker 懒加载（首次使用时初始化）
        self._reranker = None
        self._reranker_initialized = False

    @property
    def reranker(self):
        """
        懒加载 Reranker（CrossEncoder）

        依赖：sentence-transformers.CrossEncoder（完整复用，不重写）
        模型：BAAI/bge-reranker-v2-m3（通过 settings 配置）
        设备：自动检测 CPU/GPU/MPS
        """
        if self._reranker_initialized:
            return self._reranker

        self._reranker_initialized = True

        if not settings.RERANKER_ENABLED:
            logger.info("Reranker 已禁用 (RERANKER_ENABLED=false)")
            return None

        try:
            # 强依赖：sentence-transformers.CrossEncoder
            from sentence_transformers import CrossEncoder

            device = _get_reranker_device()

            # 优先尝试离线加载（模型已下载到 HF_HOME/MODELS_DIR）
            try:
                self._reranker = CrossEncoder(
                    settings.RERANKER_MODEL,
                    max_length=settings.RERANKER_MAX_LENGTH,
                    device=device,
                    trust_remote_code=True,
                    local_files_only=True
                )
                logger.info(f"✅ Reranker 加载完成: {settings.RERANKER_MODEL} (离线, {device})")
            except Exception:
                # 离线失败，在线下载
                logger.info(f"Reranker 模型未找到，正在下载: {settings.RERANKER_MODEL}")
                self._reranker = CrossEncoder(
                    settings.RERANKER_MODEL,
                    max_length=settings.RERANKER_MAX_LENGTH,
                    device=device,
                    trust_remote_code=True
                )
                logger.info(f"✅ Reranker 加载完成: {settings.RERANKER_MODEL} (已下载, {device})")

        except ImportError:
            logger.warning("sentence-transformers 未安装，Reranker 不可用")
            self._reranker = None
        except Exception as e:
            logger.error(f"Reranker 初始化失败: {e}")
            self._reranker = None

        return self._reranker

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
        混合检索：Dense + BM25 双路召回 + RRF 融合 + CrossEncoder 重排序

        流程：
        1. Dense（向量）召回 Top-N
        2. BM25（稀疏）召回 Top-N
        3. RRF 融合两路结果
        4. CrossEncoder 精排序（如果可用）

        依赖：
        - sentence-transformers.CrossEncoder（完整复用）
        - rank_bm25.BM25Plus（完整复用）
        """
        use_reranker = self.reranker is not None
        # 召回更多候选用于融合和重排序
        fetch_k = k * 10 if use_reranker else k * 5

        # ========== 1. Dense（向量）召回 ==========
        retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": fetch_k, "filter": metadata_filter} if metadata_filter else {"k": fetch_k}
        )
        dense_results = retriever.invoke(query)

        if not dense_results:
            logger.info(f"No documents found for query: {query}")
            return []

        # ========== 2. BM25（稀疏）召回 ==========
        bm25_results = []
        try:
            from rank_bm25 import BM25Plus

            # 使用 keywords（如果提供）或 query 分词
            query_tokens = keywords if keywords else query.lower().split()
            doc_tokens = [doc.page_content.lower().split() for doc in dense_results]

            bm25 = BM25Plus(doc_tokens)
            bm25_scores = bm25.get_scores(query_tokens)

            # 按 BM25 分数排序
            bm25_ranked = sorted(zip(dense_results, bm25_scores), key=lambda x: x[1], reverse=True)
            bm25_results = [doc for doc, _ in bm25_ranked[:fetch_k]]

            logger.debug(f"BM25 召回: {len(bm25_results)} docs")

        except ImportError:
            logger.warning("rank_bm25 未安装，跳过 BM25 召回")
            bm25_results = []
        except Exception as e:
            logger.warning(f"BM25 召回失败: {e}")
            bm25_results = []

        # ========== 3. RRF 融合 ==========
        candidates = self._rrf_fusion(dense_results, bm25_results, k=60)
        logger.info(f"RRF 融合: Dense({len(dense_results)}) + BM25({len(bm25_results)}) -> {len(candidates)} docs")

        # ========== 4. CrossEncoder 精排序 ==========
        if use_reranker and candidates:
            try:
                pairs = [[query, doc.page_content] for doc in candidates]
                scores = self.reranker.predict(pairs)

                ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
                results = [doc for doc, _ in ranked[:k]]

                logger.info(f"CrossEncoder 重排序: {len(candidates)} -> {len(results)} docs")
                return results

            except Exception as e:
                logger.warning(f"CrossEncoder 重排序失败: {e}")

        # 降级：直接返回 RRF 融合结果
        return candidates[:k]

    def _rrf_fusion(self, dense_results: List[Document], bm25_results: List[Document], k: int = 60) -> List[Document]:
        """
        RRF (Reciprocal Rank Fusion) 融合算法

        公式：score(d) = Σ 1/(k + rank(d))
        k 通常取 60，用于平滑排名

        依赖：无外部依赖（纯算法）
        """
        scores = {}
        doc_map = {}

        # Dense 结果计算 RRF 分数
        for rank, doc in enumerate(dense_results):
            doc_id = id(doc)  # 使用对象 id 作为唯一标识
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            doc_map[doc_id] = doc

        # BM25 结果计算 RRF 分数
        for rank, doc in enumerate(bm25_results):
            doc_id = id(doc)
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            doc_map[doc_id] = doc

        # 按融合分数排序
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [doc_map[doc_id] for doc_id in sorted_ids]

    def update_metadata(self, source_file: str, metadata_updates: dict) -> bool:
        """
        Update metadata for all chunks of a document without re-embedding.
        Much faster than delete + re-ingest.

        Args:
            source_file: The source file path to identify chunks
            metadata_updates: Dict of metadata fields to update

        Returns:
            True if successful, False otherwise
        """
        import time
        start_time = time.time()

        try:
            # Get existing chunks
            t1 = time.time()
            data = self.vectorstore.get(where={"source_file": source_file})
            t2 = time.time()
            logger.info(f"[TIMING] vectorstore.get took {t2-t1:.3f}s")

            chunk_ids = data['ids']

            if not chunk_ids:
                logger.warning(f"No documents found for source_file: {source_file}")
                return False

            # Get existing metadata and merge updates
            existing_metadatas = data['metadatas']
            updated_metadatas = []
            for meta in existing_metadatas:
                updated_meta = {**meta, **metadata_updates}
                updated_metadatas.append(updated_meta)

            # Update metadata directly in ChromaDB (no re-embedding)
            t3 = time.time()
            self.vectorstore._collection.update(
                ids=chunk_ids,
                metadatas=updated_metadatas
            )
            t4 = time.time()
            logger.info(f"[TIMING] collection.update took {t4-t3:.3f}s")

            total_time = time.time() - start_time
            logger.info(f"Updated metadata for {len(chunk_ids)} chunks: {source_file} (total: {total_time:.3f}s)")
            return True
        except Exception as e:
            logger.error(f"Error updating metadata for {source_file}: {e}")
            return False

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
