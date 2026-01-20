# -*- coding: utf-8 -*-
"""
语义分块适配器 - Chonkie SemanticChunker

强依赖复用：
- chonkie.SemanticChunker（完整复用，不重写）
- sentence-transformers（通过 chonkie 内部调用）

本模块职责（仅胶水代码）：
- 适配 LangChain TextSplitter 接口
- 传递配置参数给 chonkie.SemanticChunker
- 不实现任何分块算法逻辑

使用方式：
    from src.services.rag.semantic_splitter import ChonkieSemanticSplitter

    splitter = ChonkieSemanticSplitter(
        embedding_model="BAAI/bge-large-zh-v1.5",
        similarity_percentile=85.0,  # 语义相似度百分位 (0-100)，内部转换为阈值
        chunk_size=2000
    )
    chunks = splitter.split_text(text)
"""

import logging
from typing import List, Optional, Any

# ========== 强依赖：完整复用，不重写 ==========
from chonkie import SemanticChunker
from langchain_text_splitters import TextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ChonkieSemanticSplitter(TextSplitter):
    """
    Chonkie SemanticChunker 的 LangChain 适配器

    强依赖：chonkie.SemanticChunker（完整复用）
    本类仅负责接口适配，不实现任何分块逻辑

    参数映射：
    - embedding_model → chonkie embedding_model
    - similarity_percentile → chonkie threshold (百分位转换为阈值 0-1)
    - chunk_size → chonkie chunk_size (最大 token 数)
    """

    def __init__(
        self,
        embedding_model: str = "BAAI/bge-large-zh-v1.5",
        similarity_percentile: float = 85.0,
        chunk_size: int = 2000,
        similarity_window: int = 3,
        min_sentences_per_chunk: int = 1,
        **kwargs: Any
    ):
        """
        初始化语义分块器

        Args:
            embedding_model: Embedding 模型名称（使用项目 BAAI/bge-large-zh-v1.5）
            similarity_percentile: 语义相似度百分位阈值 (0-100)，越高分块越细
                                   内部转换为 chonkie threshold (0-1)
            chunk_size: 最大块大小（token 数）
            similarity_window: 相似度计算窗口大小
            min_sentences_per_chunk: 每块最少句子数
            **kwargs: 传递给 TextSplitter 的其他参数
        """
        super().__init__(**kwargs)

        self._embedding_model = embedding_model
        # 将百分位 (0-100) 转换为阈值 (0-1)
        # 例如: 85.0 → 0.85
        self._threshold = similarity_percentile / 100.0
        self._similarity_percentile = similarity_percentile
        self._chunk_size = chunk_size
        self._similarity_window = similarity_window
        self._min_sentences_per_chunk = min_sentences_per_chunk

        # 延迟初始化 chunker（避免导入时加载模型）
        self._chunker: Optional[SemanticChunker] = None

        logger.info(
            f"ChonkieSemanticSplitter 配置: "
            f"model={embedding_model}, percentile={similarity_percentile}, chunk_size={chunk_size}"
        )

    @property
    def chunker(self) -> SemanticChunker:
        """
        懒加载 Chonkie SemanticChunker

        强依赖：chonkie.SemanticChunker（完整复用，不重写）
        """
        if self._chunker is None:
            logger.info(f"初始化 Chonkie SemanticChunker (model={self._embedding_model})...")

            # 完整复用 chonkie.SemanticChunker，仅传递参数
            self._chunker = SemanticChunker(
                embedding_model=self._embedding_model,
                threshold=self._threshold,
                chunk_size=self._chunk_size,
                similarity_window=self._similarity_window,
                min_sentences_per_chunk=self._min_sentences_per_chunk,
            )

            logger.info("✅ Chonkie SemanticChunker 初始化完成")

        return self._chunker

    def split_text(self, text: str) -> List[str]:
        """
        将文本按语义边界分块

        强依赖：chonkie.SemanticChunker.chunk（完整复用）
        本方法仅做接口适配，不实现分块逻辑

        Args:
            text: 待分块的文本

        Returns:
            List[str]: 分块后的文本列表
        """
        if not text or not text.strip():
            return []

        try:
            # 调用 chonkie.SemanticChunker.chunk（完整复用）
            chunks = self.chunker.chunk(text)

            # 提取文本内容（chonkie 返回 Chunk 对象列表）
            result = [chunk.text for chunk in chunks if chunk.text.strip()]

            logger.debug(f"语义分块完成: {len(text)} chars → {len(result)} chunks")
            return result

        except Exception as e:
            logger.error(f"语义分块失败: {e}")
            # 降级：返回原文作为单块
            return [text]

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        将文档列表按语义边界分块

        Args:
            documents: 待分块的文档列表

        Returns:
            List[Document]: 分块后的文档列表（保留原始 metadata）
        """
        result = []
        for doc in documents:
            chunks = self.split_text(doc.page_content)
            for i, chunk_text in enumerate(chunks):
                # 复制 metadata 并添加块索引
                new_metadata = doc.metadata.copy()
                new_metadata["chunk_index"] = i
                result.append(Document(page_content=chunk_text, metadata=new_metadata))
        return result


def create_semantic_splitter(
    embedding_model: str = "auto",
    threshold: float = 0.5,
    chunk_size: int = 2000,
) -> ChonkieSemanticSplitter:
    """
    工厂函数：创建语义分块器

    Args:
        embedding_model: Embedding 模型（"auto" 使用项目默认模型）
        threshold: 语义相似度阈值 (0-1)
        chunk_size: 最大块大小

    Returns:
        ChonkieSemanticSplitter: 语义分块器实例
    """
    from config.settings import settings

    # 解析 "auto" 为项目默认模型
    if embedding_model.lower() == "auto":
        embedding_model = settings.EMBEDDING_MODEL

    return ChonkieSemanticSplitter(
        embedding_model=embedding_model,
        threshold=threshold,
        chunk_size=chunk_size,
    )