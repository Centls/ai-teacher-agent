# -*- coding: utf-8 -*-
"""
多模态 RAG Pipeline 扩展

扩展现有 RAGPipeline，增加图片、音频等多模态文件处理能力。
采用强依赖复用原则，直接调用多模态子服务，不实现任何处理逻辑。

依赖来源：
    - 文档处理: 现有 RAGPipeline (LangChain loaders)
    - 图片 OCR: PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR)
    - 音频 ASR: FunASR (https://github.com/modelscope/FunASR)
"""

import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from langchain_core.documents import Document

from .pipeline import RAGPipeline
from src.services.multimodal.sync_client import MultimodalSyncClient, ProcessResult

logger = logging.getLogger(__name__)


class MultimodalRAGPipeline(RAGPipeline):
    """
    多模态 RAG Pipeline

    继承自 RAGPipeline，扩展支持图片和音频文件。
    对于图片/音频，调用多模态子服务进行处理，
    然后将提取的文本存入向量数据库。

    使用示例：
        pipeline = MultimodalRAGPipeline()

        # 处理 PDF（使用父类方法）
        pipeline.ingest("data/doc.pdf")

        # 处理图片（调用 OCR 服务）
        pipeline.ingest("data/image.png")

        # 处理音频（调用 ASR 服务）
        pipeline.ingest("data/audio.mp3")
    """

    # 多模态文件格式
    MULTIMODAL_FORMATS = {
        # 图片格式
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff",
        # 音频格式
        ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma",
    }

    def __init__(self, vector_db_path: str = "./chroma_db", chunking_strategy: str = "auto"):
        """
        初始化多模态 RAG Pipeline

        Args:
            vector_db_path: ChromaDB 持久化路径
            chunking_strategy: 分块策略
        """
        super().__init__(vector_db_path, chunking_strategy)

        # 初始化多模态客户端（懒加载，按需创建）
        self._multimodal_client: Optional[MultimodalSyncClient] = None

        logger.info("Initialized MultimodalRAGPipeline (extends RAGPipeline with image/audio support)")

    @property
    def multimodal_client(self) -> MultimodalSyncClient:
        """懒加载多模态客户端"""
        if self._multimodal_client is None:
            self._multimodal_client = MultimodalSyncClient()
        return self._multimodal_client

    def is_multimodal_file(self, file_path: str) -> bool:
        """判断是否是多模态文件"""
        ext = os.path.splitext(file_path)[-1].lower()
        return ext in self.MULTIMODAL_FORMATS

    def load_document(self, file_path: str) -> List[Document]:
        """
        加载文档（扩展支持多模态）

        对于传统文档格式，调用父类方法。
        对于图片/音频，调用多模态子服务提取文本。

        Args:
            file_path: 文件路径

        Returns:
            List[Document]: 文档列表
        """
        ext = os.path.splitext(file_path)[-1].lower()

        # 多模态文件：调用子服务处理
        if self.is_multimodal_file(file_path):
            return self._load_multimodal(file_path)

        # 传统文档：调用父类方法
        return super().load_document(file_path)

    def _load_multimodal(self, file_path: str) -> List[Document]:
        """
        加载多模态文件（图片/音频）

        直接调用多模态子服务，不实现任何处理逻辑。

        Args:
            file_path: 文件路径

        Returns:
            List[Document]: 包含提取文本的文档列表
        """
        ext = os.path.splitext(file_path)[-1].lower()
        file_name = os.path.basename(file_path)

        logger.info(f"Processing multimodal file: {file_name} ({ext})")

        # 调用多模态客户端处理
        result: ProcessResult = self.multimodal_client.process_file(file_path)

        if not result.success:
            logger.error(f"Multimodal processing failed: {result.error}")
            raise ValueError(f"多模态处理失败: {result.error}")

        if not result.text.strip():
            logger.warning(f"No text extracted from {file_name}")
            return []

        # 构建 Document 对象
        doc = Document(
            page_content=result.text,
            metadata={
                "source": file_path,
                "file_name": file_name,
                "file_type": ext,
                "processing_source": result.metadata.get("source", "multimodal"),
                **result.metadata
            }
        )

        logger.info(f"Extracted {len(result.text)} chars from {file_name}")
        return [doc]

    def ingest(self, file_path: str, metadata: dict = None):
        """
        导入文件到向量数据库（支持多模态）

        Args:
            file_path: 文件路径
            metadata: 附加元数据
        """
        ext = os.path.splitext(file_path)[-1].lower()

        # 多模态文件特殊处理
        if self.is_multimodal_file(file_path):
            docs = self._load_multimodal(file_path)

            if not docs:
                logger.warning(f"No content extracted from {file_path}, skipping ingest")
                return

            # 对于多模态文件，可能不需要分块（已经是完整文本）
            # 但如果文本很长，仍然需要分块
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = splitter.split_documents(docs)

            # 附加元数据
            for doc in splits:
                doc.metadata = doc.metadata or {}
                if metadata:
                    doc.metadata.update(metadata)
                doc.metadata['source_file'] = file_path

            self.vectorstore.add_documents(splits)
            logger.info(f"Ingested {len(splits)} chunks from multimodal file {file_path}")
            return

        # 传统文档：调用父类方法
        super().ingest(file_path, metadata)

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """获取所有支持的文件格式"""
        return {
            "document": [".pdf", ".docx", ".txt", ".csv", ".xlsx", ".md", ".markdown"],
            "image": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"],
            "audio": [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"],
        }
