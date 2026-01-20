import os
import logging
from typing import List, Optional
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader, TextLoader, CSVLoader, UnstructuredExcelLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from config.settings import settings, MODELS_DIR

# Parent-Child Index 依赖（强依赖复用 langchain_classic）
# ParentDocumentRetriever: 小块检索，返回大块上下文
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage import LocalFileStore, create_kv_docstore

# EnsembleRetriever 依赖（强依赖复用 langchain_classic）
# EnsembleRetriever: Dense + BM25 双路召回 + RRF 融合（内置实现）
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers.bm25 import BM25Retriever

# ChildToParentBM25Retriever: 将 BM25 子块结果升级为父块
from src.services.rag.child_to_parent_retriever import ChildToParentBM25Retriever

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

        # ========== Parent-Child Index 初始化 ==========
        # 依赖：langchain_classic.retrievers.ParentDocumentRetriever（完整复用）
        # 存储：langchain.storage.LocalFileStore（持久化父块原文）
        self._parent_retriever = None
        self._parent_retriever_initialized = False

        # ========== BM25 Retriever 初始化（用于 EnsembleRetriever）==========
        # 依赖：langchain_community.retrievers.BM25Retriever（完整复用）
        # 策略：启动时构建，ingest 时同步全量重建（内存常驻，查询零延迟）
        self._bm25_retriever = None

        # 启动时构建 BM25（如果 vectorstore 有数据）
        self._build_bm25()

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

    @property
    def parent_retriever(self):
        """
        懒加载 ParentDocumentRetriever（父子索引检索器）

        依赖：langchain_classic.retrievers.ParentDocumentRetriever（完整复用，不重写）
        存储：langchain.storage.LocalFileStore（持久化父块原文）

        原理：
        - 子块（Child）：小块，用于精确向量检索
        - 父块（Parent）：大块，返回给 LLM 提供完整上下文

        语义分块模式（SEMANTIC_CHUNKING_ENABLED=true）：
        - 父块使用 Chonkie SemanticChunker 进行语义分块
        - 依赖：chonkie.SemanticChunker（完整复用）
        """
        if self._parent_retriever_initialized:
            return self._parent_retriever

        self._parent_retriever_initialized = True

        if not settings.PARENT_CHILD_ENABLED:
            logger.info("Parent-Child Index 已禁用 (PARENT_CHILD_ENABLED=false)")
            return None

        try:
            # 确保 docstore 目录存在
            docstore_path = settings.DOCSTORE_PATH
            docstore_path.mkdir(parents=True, exist_ok=True)

            # 依赖：langchain_classic.storage.LocalFileStore + create_kv_docstore
            # LocalFileStore 存储 bytes，create_kv_docstore 包装为支持 Document 的 docstore
            file_store = LocalFileStore(str(docstore_path))
            docstore = create_kv_docstore(file_store)

            # ========== 父块分割器选择 ==========
            if settings.SEMANTIC_CHUNKING_ENABLED:
                # 语义分块模式：使用 Chonkie SemanticChunker
                # 依赖：chonkie.SemanticChunker（通过适配器完整复用）
                try:
                    from src.services.rag.semantic_splitter import ChonkieSemanticSplitter

                    # 确定 embedding 模型
                    embedding_model = settings.SEMANTIC_EMBEDDING_MODEL
                    if embedding_model.lower() == "auto":
                        embedding_model = settings.EMBEDDING_MODEL

                    parent_splitter = ChonkieSemanticSplitter(
                        embedding_model=embedding_model,
                        similarity_percentile=settings.SEMANTIC_SIMILARITY_PERCENTILE,
                        chunk_size=settings.SEMANTIC_CHUNK_SIZE,
                    )
                    logger.info(
                        f"✅ 语义分块模式: Chonkie SemanticChunker "
                        f"(model={embedding_model}, percentile={settings.SEMANTIC_SIMILARITY_PERCENTILE})"
                    )
                except ImportError as e:
                    logger.warning(f"Chonkie 不可用，降级为固定分块: {e}")
                    parent_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=settings.PARENT_CHUNK_SIZE,
                        chunk_overlap=settings.PARENT_CHUNK_OVERLAP
                    )
                except Exception as e:
                    logger.warning(f"语义分块初始化失败，降级为固定分块: {e}")
                    parent_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=settings.PARENT_CHUNK_SIZE,
                        chunk_overlap=settings.PARENT_CHUNK_OVERLAP
                    )
            else:
                # 传统固定分块模式
                parent_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=settings.PARENT_CHUNK_SIZE,
                    chunk_overlap=settings.PARENT_CHUNK_OVERLAP
                )
                logger.info(f"固定分块模式: Parent({settings.PARENT_CHUNK_SIZE})")

            # 子块分割器（小块，用于向量检索）- 始终使用固定分块
            child_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHILD_CHUNK_SIZE,
                chunk_overlap=settings.CHILD_CHUNK_OVERLAP
            )

            # 依赖：langchain_classic.retrievers.ParentDocumentRetriever（完整复用）
            self._parent_retriever = ParentDocumentRetriever(
                vectorstore=self.vectorstore,
                docstore=docstore,
                child_splitter=child_splitter,
                parent_splitter=parent_splitter,
            )

            logger.info(
                f"✅ Parent-Child Index 初始化完成: "
                f"Parent({'Semantic' if settings.SEMANTIC_CHUNKING_ENABLED else settings.PARENT_CHUNK_SIZE}), "
                f"Child({settings.CHILD_CHUNK_SIZE})"
            )

        except Exception as e:
            logger.error(f"Parent-Child Index 初始化失败: {e}")
            self._parent_retriever = None

        return self._parent_retriever

    @property
    def bm25_retriever(self):
        """
        获取 BM25Retriever（稀疏检索器）

        依赖：langchain_community.retrievers.BM25Retriever（完整复用，不重写）

        策略：
        - 启动时从 vectorstore 全量加载并构建（__init__ 中调用 _build_bm25）
        - ingest 时同步全量重建（调用 _build_bm25）
        - 常驻内存，检索时零延迟
        """
        return self._bm25_retriever

    def _build_bm25(self):
        """
        从 vectorstore 全量重建 BM25 索引

        调用时机：
        - 启动时（__init__）
        - 每次 ingest 后（同步重建）

        性能：
        - 1万篇文档约 几百毫秒 ~ 1秒
        - 10万篇文档约 几秒
        - 宁可 ingest 慢 1秒，也不让 retrieve 慢 1秒
        """
        try:
            data = self.vectorstore.get()

            if not data['documents']:
                logger.info("Vectorstore 为空，BM25Retriever 待首次 ingest 后构建")
                self._bm25_retriever = None
                return

            # 从 vectorstore 重建 Document 对象列表
            docs = []
            for i, content in enumerate(data['documents']):
                metadata = data['metadatas'][i] if data['metadatas'] else {}
                docs.append(Document(page_content=content, metadata=metadata))

            # 全量重建 BM25Retriever
            self._bm25_retriever = BM25Retriever.from_documents(docs)
            logger.info(f"✅ BM25Retriever 构建完成: {len(docs)} 文档")

        except Exception as e:
            logger.error(f"BM25Retriever 构建失败: {e}")
            self._bm25_retriever = None

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

        如果启用父子索引（PARENT_CHILD_ENABLED=true）：
        - 使用 ParentDocumentRetriever.add_documents（自动分父块/子块）
        - 子块存入向量库，父块存入 DocStore

        否则使用传统单层分块。
        """
        docs = self.load_document(file_path)

        # 附加文件级 metadata
        for doc in docs:
            doc.metadata = doc.metadata or {}
            if metadata:
                doc.metadata.update(metadata)
            doc.metadata['source_file'] = file_path

        # ========== 父子索引模式 ==========
        if self.parent_retriever is not None:
            # 依赖：ParentDocumentRetriever.add_documents（完整复用）
            # 自动完成：父块分割 → 子块分割 → 子块向量化 → 父块存储
            self.parent_retriever.add_documents(docs, ids=None)
            self._build_bm25()  # 同步全量重建 BM25
            logger.info(f"✅ [Parent-Child] Ingested from {file_path}")
            return

        # ========== 传统单层分块模式 ==========
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
        self._build_bm25()  # 同步全量重建 BM25
        logger.info(f"Ingested {len(splits)} chunks from {file_path}")

    def ingest_text(self, text: str, metadata: dict = None):
        """
        Ingest raw text.
        支持父子索引模式 (PARENT_CHILD_ENABLED=true)
        """
        doc = Document(page_content=text, metadata=metadata or {})
        docs = [doc]

        # ========== 父子索引模式 ==========
        if self.parent_retriever is not None:
            # 依赖：ParentDocumentRetriever.add_documents（完整复用）
            self.parent_retriever.add_documents(docs, ids=None)
            self._build_bm25()  # 同步全量重建 BM25
            logger.info(f"✅ [Parent-Child] Ingested text ({len(text)} chars)")
            return

        # ========== 传统模式 ==========
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = splitter.split_documents(docs)
        self.vectorstore.add_documents(splits)
        self._build_bm25()  # 同步全量重建 BM25
        logger.info(f"Ingested {len(splits)} chunks from raw text")

    def retrieve(self, query: str, k: int = 4, keywords: Optional[list] = None, metadata_filter: Optional[dict] = None) -> List[Document]:
        """
        混合检索：EnsembleRetriever (Dense + BM25 RRF 融合) + CrossEncoder 重排序

        如果启用父子索引（PARENT_CHILD_ENABLED=true）：
        - 使用 ParentDocumentRetriever 检索（小块匹配，返回大块上下文）

        流程：
        1. EnsembleRetriever 融合召回（Dense + BM25，内置 RRF 算法）
        2. CrossEncoder 精排序（如果可用）

        依赖：
        - langchain.retrievers.EnsembleRetriever（RRF 融合，完整复用）
        - langchain_community.retrievers.BM25Retriever（稀疏检索，完整复用）
        - langchain_classic.retrievers.ParentDocumentRetriever（父子索引，完整复用）
        - sentence-transformers.CrossEncoder（重排序，完整复用）

        注意：keywords 参数已弃用，BM25Retriever 内部自动处理分词
        """
        # keywords 参数已弃用警告
        if keywords is not None:
            logger.warning("keywords 参数已弃用，BM25Retriever 内部自动处理分词")

        use_reranker = self.reranker is not None
        use_parent_child = self.parent_retriever is not None

        # 召回更多候选用于重排序
        fetch_k = k * 10 if use_reranker else k * 5

        # ========== 1. EnsembleRetriever 融合召回 ==========
        try:
            candidates = self._ensemble_retrieve(query, fetch_k, use_parent_child, metadata_filter)
        except Exception as e:
            logger.warning(f"EnsembleRetriever 失败，降级为纯向量检索: {e}")
            candidates = self._fallback_dense_retrieve(query, fetch_k, use_parent_child, metadata_filter)

        if not candidates:
            logger.info(f"No documents found for query: {query}")
            return []

        # ========== 2. CrossEncoder 精排序 ==========
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

        # 降级：直接返回 EnsembleRetriever 结果
        return candidates[:k]

    def _ensemble_retrieve(
        self,
        query: str,
        fetch_k: int,
        use_parent_child: bool,
        metadata_filter: Optional[dict] = None
    ) -> List[Document]:
        """
        使用 EnsembleRetriever 进行 Dense + BM25 融合检索

        依赖：
        - langchain.retrievers.EnsembleRetriever（内置 RRF 融合，完整复用）
        - ChildToParentBM25Retriever（Parent-Child 模式下升级子块为父块）

        Parent-Child 模式特殊处理：
        - Dense 路径：ParentDocumentRetriever 直接返回父块
        - BM25 路径：ChildToParentBM25Retriever 包装器将子块升级为父块
        - 确保两条路径返回相同粒度的文档，RRF 融合结果一致
        """
        # 构建 Dense Retriever
        if use_parent_child:
            # Parent-Child 模式：使用 ParentDocumentRetriever
            dense_retriever = self.parent_retriever
        else:
            # 传统模式：使用 vectorstore retriever
            dense_retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": fetch_k, "filter": metadata_filter} if metadata_filter else {"k": fetch_k}
            )

        # 获取 BM25 Retriever
        raw_bm25_retriever = self.bm25_retriever

        if raw_bm25_retriever is None:
            # BM25 不可用，降级为纯向量检索
            logger.info("BM25Retriever 不可用，使用纯向量检索")
            results = dense_retriever.invoke(query)
            return results[:fetch_k]

        # ========== Parent-Child 模式：包装 BM25 为 ChildToParentBM25Retriever ==========
        if use_parent_child and self.parent_retriever is not None:
            # 获取 docstore（从 ParentDocumentRetriever 内部获取）
            docstore = self.parent_retriever.docstore

            # 包装 BM25Retriever，使其返回父块而非子块
            bm25_retriever = ChildToParentBM25Retriever(
                bm25_retriever=raw_bm25_retriever,
                docstore=docstore,
                k=fetch_k
            )
            logger.info("Parent-Child 模式：使用 ChildToParentBM25Retriever 包装器")
        else:
            # 传统模式：直接使用 BM25Retriever
            bm25_retriever = raw_bm25_retriever
            bm25_retriever.k = fetch_k

        # 依赖：langchain.retrievers.EnsembleRetriever（完整复用）
        # weights: [dense_weight, bm25_weight]，默认各 0.5
        ensemble_retriever = EnsembleRetriever(
            retrievers=[dense_retriever, bm25_retriever],
            weights=[0.5, 0.5]  # RRF 融合权重
        )

        results = ensemble_retriever.invoke(query)
        logger.info(f"EnsembleRetriever 融合检索: {len(results)} docs (Dense + BM25 RRF)")

        return results[:fetch_k]

    def _fallback_dense_retrieve(
        self,
        query: str,
        fetch_k: int,
        use_parent_child: bool,
        metadata_filter: Optional[dict] = None
    ) -> List[Document]:
        """
        降级检索：仅使用 Dense（向量）检索
        """
        if use_parent_child:
            results = self.parent_retriever.invoke(query)
        else:
            retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": fetch_k, "filter": metadata_filter} if metadata_filter else {"k": fetch_k}
            )
            results = retriever.invoke(query)

        logger.info(f"降级 Dense 检索: {len(results)} docs")
        return results[:fetch_k]

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

        Parent-Child 模式下同步清理：
        1. 从向量库删除子块（Child Chunks）
        2. 从 docstore 删除关联的父块（Parent Chunks）

        父块清理策略：
        - 从子块 metadata 中提取 doc_id（父块 ID）
        - 使用 docstore.mdelete 批量删除父块文件
        """
        try:
            # 1. Find IDs to delete
            # Note: LangChain's Chroma wrapper uses 'where' for metadata filtering in get()
            data = self.vectorstore.get(where={"source_file": source_file})
            ids_to_delete = data['ids']
            metadatas = data.get('metadatas', [])

            if not ids_to_delete:
                logger.warning(f"No documents found for source_file: {source_file}")
                return False

            # 2. 提取关联的父块 ID（Parent-Child 模式）
            parent_ids_to_delete = set()
            if metadatas:
                for meta in metadatas:
                    if meta and 'doc_id' in meta:
                        parent_ids_to_delete.add(meta['doc_id'])

            # 3. Delete child chunks from vectorstore
            self.vectorstore.delete(ids=ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} child chunks for source_file: {source_file}")

            # 4. Delete parent chunks from docstore (Parent-Child 模式)
            if parent_ids_to_delete and self.parent_retriever is not None:
                try:
                    docstore = self.parent_retriever.docstore
                    # 使用 mdelete 批量删除父块
                    docstore.mdelete(list(parent_ids_to_delete))
                    logger.info(f"Deleted {len(parent_ids_to_delete)} parent chunks from docstore")
                except Exception as e:
                    logger.warning(f"Failed to delete parent chunks from docstore: {e}")
                    # 父块删除失败不影响主流程，子块已删除

            # 5. 同步重建 BM25 索引
            self._build_bm25()

            return True
        except Exception as e:
            logger.error(f"Error deleting document {source_file}: {e}")
            return False
