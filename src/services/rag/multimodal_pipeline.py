# -*- coding: utf-8 -*-
"""
Multimodal RAG Pipeline

Extends RAGPipeline with multimodal file processing capability.
All processing is delegated to Docling service (which handles docs, images, and audio).

继承自 RAGPipeline 的高级检索功能：
    - Parent-Child Index（父子索引）：小块检索 → 返回大块上下文
    - RRF Fusion（倒数排名融合）：Dense + BM25 双路召回融合
    - CrossEncoder Reranking（重排序）：BGE-Reranker-v2-m3 精排

External Dependencies:
    - Docling Service (unified document/OCR/ASR)
    - LangChain (fallback for text formats)
    - langchain_classic.retrievers.ParentDocumentRetriever（父子索引，完整复用）
    - sentence-transformers.CrossEncoder（重排序，完整复用）
    - rank_bm25.BM25Plus（稀疏检索，完整复用）
"""

import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from langchain_core.documents import Document

from .pipeline import RAGPipeline
from src.services.multimodal.sync_client import MultimodalSyncClient, ProcessResult
from src.services.multimodal.client import MultimodalClient

# 使用统一日志配置
try:
    from src.core.logging_config import get_docling_logger, get_rag_logger
    docling_logger = get_docling_logger()
    rag_logger = get_rag_logger()
except ImportError:
    # Fallback to standard logging if logging_config not available
    docling_logger = logging.getLogger("docling")
    rag_logger = logging.getLogger("rag")

logger = logging.getLogger(__name__)


class MultimodalRAGPipeline(RAGPipeline):
    """
    Multimodal RAG Pipeline

    Extends RAGPipeline with support for documents, images, and audio via Docling service.

    Usage:
        pipeline = MultimodalRAGPipeline()
        pipeline.ingest("data/doc.pdf")      # PDF via Docling (fallback to LangChain)
        pipeline.ingest("data/image.png")    # Image OCR via Docling
        pipeline.ingest("data/audio.mp3")    # Audio ASR via Docling (Whisper)
    """

    # Formats handled by Docling service
    DOCLING_FORMATS = {
        # Documents
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
        ".html", ".htm", ".md", ".markdown",
        # Images
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif",
        # Audio (via Whisper integration in Docling service)
        ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"
    }

    # Text formats handled by parent class (LangChain)
    TEXT_FORMATS = {".txt", ".csv"}

    def __init__(self, vector_db_path: str = "./data/chroma_db", chunking_strategy: str = "auto"):
        """
        Initialize Multimodal RAG Pipeline

        Args:
            vector_db_path: ChromaDB persistence path
            chunking_strategy: Chunking strategy
        """
        super().__init__(vector_db_path, chunking_strategy)
        self._multimodal_client: Optional[MultimodalSyncClient] = None
        self._async_multimodal_client: Optional[MultimodalClient] = None
        logger.info("Initialized MultimodalRAGPipeline (Docling-based)")

    @property
    def multimodal_client(self) -> MultimodalSyncClient:
        """Lazy-load multimodal client (sync)"""
        if self._multimodal_client is None:
            self._multimodal_client = MultimodalSyncClient()
        return self._multimodal_client

    @property
    def async_multimodal_client(self) -> MultimodalClient:
        """Lazy-load multimodal client (async)"""
        if self._async_multimodal_client is None:
            self._async_multimodal_client = MultimodalClient()
        return self._async_multimodal_client

    def is_multimodal_file(self, file_path: str) -> bool:
        """Check if file should be processed by Docling"""
        ext = os.path.splitext(file_path)[-1].lower()
        return ext in self.DOCLING_FORMATS

    def load_document(self, file_path: str) -> List[Document]:
        """
        Load document (auto-select processor)

        Processing priority:
        1. Docling formats (PDF/DOCX/images/audio) -> Docling service
        2. Fallback: If Docling fails, try standard LangChain loaders for PDF/DOCX
        3. Text formats (TXT/CSV) -> Parent class (LangChain)

        Args:
            file_path: File path

        Returns:
            List[Document]: Document list
        """
        ext = os.path.splitext(file_path)[-1].lower()

        # Text formats: use parent class directly
        if ext in self.TEXT_FORMATS:
            return super().load_document(file_path)

        # Docling formats: call Docling service with fallback
        if ext in self.DOCLING_FORMATS:
            try:
                return self._load_via_docling(file_path)
            except Exception as e:
                # Fallback to parent for some document formats (PDF, DOCX)
                # Parent class uses PyPDFLoader, UnstructuredWordDocumentLoader, etc.
                if ext in {".pdf", ".docx", ".doc", ".xlsx", ".csv", ".txt", ".md"}:
                    logger.warning(f"Docling failed for {file_path}: {e}. Fallback to LangChain loader.")
                    return super().load_document(file_path)

                # For images/audio, no standard fallback exists in parent, so re-raise
                logger.error(f"Docling processing failed for {file_path} and no fallback available: {e}")
                raise

        # Other formats: try parent class
        return super().load_document(file_path)

    def _load_via_docling(self, file_path: str) -> List[Document]:
        """
        Load file via Docling service.

        All processing logic is in Docling service (server-side).
        This method only handles HTTP call orchestration.
        """
        import time
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[-1].lower()
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        docling_logger.info(f"开始解析 | file={file_name} | type={ext} | size={file_size/1024:.1f}KB")
        start_time = time.time()

        # Call Docling service
        result: ProcessResult = self.multimodal_client.process_file(file_path)
        duration = time.time() - start_time

        if not result.success:
            docling_logger.error(f"解析失败 | file={file_name} | duration={duration:.2f}s | error={result.error}")
            raise ValueError(f"Docling service returned error: {result.error}")

        if not result.text.strip():
            docling_logger.warning(f"无文本提取 | file={file_name} | duration={duration:.2f}s")
            return []

        # Build Document object
        doc = Document(
            page_content=result.text,
            metadata={
                "source": file_path,
                "file_name": file_name,
                "file_type": ext,
                "processing_source": "docling_service",
                **result.metadata
            }
        )

        docling_logger.info(f"解析完成 | file={file_name} | chars={len(result.text)} | duration={duration:.2f}s")
        return [doc]

    def ingest(self, file_path: str, metadata: dict = None):
        """
        Ingest file to vector database (multimodal support)

        支持父子索引模式（Parent-Child Index）：
        - 如果启用父子索引（PARENT_CHILD_ENABLED=true）：
          使用 ParentDocumentRetriever.add_documents（自动分父块/子块）
        - 否则使用传统单层分块

        依赖：
        - langchain_classic.retrievers.ParentDocumentRetriever（完整复用，继承自父类）

        Args:
            file_path: File path
            metadata: Additional metadata
        """
        # Unified loading logic with fallback support
        try:
            docs = self.load_document(file_path)
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
            return

        if not docs:
            logger.warning(f"No content extracted from {file_path}, skipping")
            return

        # 附加文件级 metadata（包括多模态处理来源）
        for doc in docs:
            doc.metadata = doc.metadata or {}
            if metadata:
                doc.metadata.update(metadata)
            doc.metadata['source_file'] = file_path

        # 策略优化：将复杂元数据序列化为 JSON 字符串，而不是直接丢弃
        # 这样既满足 ChromaDB 的扁平化要求，又保留了 Docling 的 pages/tables 等结构化信息
        import json
        for doc in docs:
            # 遍历元数据副本，避免在迭代时修改字典大小
            for key, value in list(doc.metadata.items()):
                if isinstance(value, (dict, list)):
                    try:
                        # 尝试转为 JSON 字符串，保留中文可读性
                        doc.metadata[key] = json.dumps(value, ensure_ascii=False)
                    except Exception as e:
                        # 如果序列化失败，降级为普通字符串
                        logger.warning(f"Metadata serialization failed for {key}: {e}")
                        doc.metadata[key] = str(value)

        # 清洗复杂元数据 (作为最后一道防线，防止漏网之鱼)
        # 依赖：langchain_community.vectorstores.utils.filter_complex_metadata
        try:
            from langchain_community.vectorstores.utils import filter_complex_metadata
            docs = filter_complex_metadata(docs)
        except ImportError:
            logger.warning("langchain_community not found, skipping metadata filtering")
        except Exception as e:
            logger.warning(f"Metadata filtering failed: {e}")

        # ========== 父子索引模式 ==========
        # 依赖：ParentDocumentRetriever（继承自父类 RAGPipeline）
        if self.parent_retriever is not None:
            # 依赖：ParentDocumentRetriever.add_documents（完整复用）
            # 自动完成：父块分割 → 子块分割 → 子块向量化 → 父块存储
            self.parent_retriever.add_documents(docs, ids=None)
            self._build_bm25()  # 同步全量重建 BM25
            logger.info(f"✅ [Parent-Child][Multimodal] Ingested from {file_path}")
            return

        # ========== 传统单层分块模式 ==========
        # Chunk documents
        # For Docling results (often markdown), we might want smarter chunking,
        # but for consistency we use the same strategy as parent or simple recursive.

        # Check if we should use parent's strategy logic
        splitter = self._get_text_splitter(docs, file_path)

        # MarkdownHeaderTextSplitter expects string, not documents
        from langchain_text_splitters import MarkdownHeaderTextSplitter
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

            # Preserve processing source if present (e.g. from Docling)
            if docs and 'processing_source' in docs[0].metadata:
                doc.metadata['processing_source'] = docs[0].metadata['processing_source']

        self.vectorstore.add_documents(splits)
        self._build_bm25()  # 同步全量重建 BM25
        logger.info(f"Ingested {len(splits)} chunks from {file_path}")

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """Get all supported file formats"""
        return {
            "document": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".html", ".md"],
            "image": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif"],
            "audio": [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"]
        }

    # ========== 异步方法（非阻塞，用于 FastAPI 端点）==========

    async def async_load_document(self, file_path: str) -> List[Document]:
        """
        异步加载文档（非阻塞）

        Processing priority:
        1. Docling formats (PDF/DOCX/images/audio) -> Docling service (async)
        2. Fallback: If Docling fails, try standard LangChain loaders for PDF/DOCX
        3. Text formats (TXT/CSV) -> Parent class (LangChain, sync in thread)

        Args:
            file_path: File path

        Returns:
            List[Document]: Document list
        """
        import asyncio

        ext = os.path.splitext(file_path)[-1].lower()

        # Text formats: use parent class in thread pool (避免阻塞事件循环)
        if ext in self.TEXT_FORMATS:
            return await asyncio.to_thread(super().load_document, file_path)

        # Docling formats: call Docling service with async client
        if ext in self.DOCLING_FORMATS:
            try:
                return await self._async_load_via_docling(file_path)
            except Exception as e:
                # Fallback to parent for some document formats (PDF, DOCX)
                if ext in {".pdf", ".docx", ".doc", ".xlsx", ".csv", ".txt", ".md"}:
                    logger.warning(f"Docling async failed for {file_path}: {e}. Fallback to LangChain loader.")
                    return await asyncio.to_thread(super().load_document, file_path)

                # For images/audio, no standard fallback exists in parent, so re-raise
                logger.error(f"Docling async processing failed for {file_path} and no fallback available: {e}")
                raise

        # Other formats: try parent class in thread pool
        return await asyncio.to_thread(super().load_document, file_path)

    async def _async_load_via_docling(self, file_path: str) -> List[Document]:
        """
        异步加载文件（通过 Docling 服务）

        使用 httpx.AsyncClient，不阻塞事件循环。
        """
        import time
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[-1].lower()
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        docling_logger.info(f"开始解析(异步) | file={file_name} | type={ext} | size={file_size/1024:.1f}KB")
        start_time = time.time()

        # 调用异步客户端
        result = await self.async_multimodal_client.process_file(file_path)
        duration = time.time() - start_time

        if not result.success:
            docling_logger.error(f"解析失败(异步) | file={file_name} | duration={duration:.2f}s | error={result.error}")
            raise ValueError(f"Docling service returned error: {result.error}")

        if not result.text.strip():
            docling_logger.warning(f"无文本提取(异步) | file={file_name} | duration={duration:.2f}s")
            return []

        # Build Document object
        doc = Document(
            page_content=result.text,
            metadata={
                "source": file_path,
                "file_name": file_name,
                "file_type": ext,
                "processing_source": "docling_service_async",
                **result.metadata
            }
        )

        docling_logger.info(f"解析完成(异步) | file={file_name} | chars={len(result.text)} | duration={duration:.2f}s")
        return [doc]

    async def async_ingest(self, file_path: str, metadata: dict = None):
        """
        异步 Ingest 文件到向量库（非阻塞）

        使用异步客户端调用 Docling 服务，不阻塞主事件循环。
        其他请求（如 /threads、/health）可以正常响应。

        支持父子索引模式（Parent-Child Index）：
        - 如果启用父子索引（PARENT_CHILD_ENABLED=true）：
          使用 ParentDocumentRetriever.add_documents（自动分父块/子块）
        - 否则使用传统单层分块

        Args:
            file_path: File path
            metadata: Additional metadata
        """
        import asyncio
        import json

        # 异步加载文档（Docling 调用不阻塞）
        try:
            docs = await self.async_load_document(file_path)
        except Exception as e:
            logger.error(f"Failed to async load document {file_path}: {e}")
            return

        if not docs:
            logger.warning(f"No content extracted from {file_path}, skipping")
            return

        # 附加文件级 metadata
        for doc in docs:
            doc.metadata = doc.metadata or {}
            if metadata:
                doc.metadata.update(metadata)
            doc.metadata['source_file'] = file_path

        # 序列化复杂元数据
        for doc in docs:
            for key, value in list(doc.metadata.items()):
                if isinstance(value, (dict, list)):
                    try:
                        doc.metadata[key] = json.dumps(value, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(f"Metadata serialization failed for {key}: {e}")
                        doc.metadata[key] = str(value)

        # 清洗复杂元数据
        try:
            from langchain_community.vectorstores.utils import filter_complex_metadata
            docs = filter_complex_metadata(docs)
        except ImportError:
            logger.warning("langchain_community not found, skipping metadata filtering")
        except Exception as e:
            logger.warning(f"Metadata filtering failed: {e}")

        # ========== 向量化和索引（CPU 密集型，放到线程池）==========
        # 注意：ChromaDB 和 embedding 计算是同步阻塞的，需要在线程池中执行
        await asyncio.to_thread(self._do_ingest, docs, file_path, metadata)

    def _do_ingest(self, docs: List[Document], file_path: str, metadata: dict = None):
        """
        实际执行向量化和索引的同步方法（在线程池中调用）

        Args:
            docs: 已加载的文档列表
            file_path: 原始文件路径
            metadata: 额外元数据
        """
        # ========== 父子索引模式 ==========
        if self.parent_retriever is not None:
            self.parent_retriever.add_documents(docs, ids=None)
            self._build_bm25()
            logger.info(f"✅ [Parent-Child][Multimodal][Async] Ingested from {file_path}")
            return

        # ========== 传统单层分块模式 ==========
        from langchain_text_splitters import MarkdownHeaderTextSplitter

        splitter = self._get_text_splitter(docs, file_path)

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

            if docs and 'processing_source' in docs[0].metadata:
                doc.metadata['processing_source'] = docs[0].metadata['processing_source']

        self.vectorstore.add_documents(splits)
        self._build_bm25()
        logger.info(f"Ingested {len(splits)} chunks from {file_path} (async)")
