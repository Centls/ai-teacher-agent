# -*- coding: utf-8 -*-
"""
Child-to-Parent BM25 Retriever Wrapper

将 BM25Retriever 的子块检索结果"升级"为父块，
确保与 ParentDocumentRetriever 的 Dense 检索结果一致。

原理：
1. BM25Retriever 检索子块（Child Chunks）
2. 从子块 metadata 中提取 doc_id（父块 ID）
3. 从 docstore 中查找对应的父块（Parent Chunks）
4. 返回去重后的父块列表

依赖：
- langchain_community.retrievers.bm25.BM25Retriever（稀疏检索）
- langchain_core.stores.BaseStore（docstore 抽象）
"""

import logging
from typing import List, Optional, Any, Sequence

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

logger = logging.getLogger(__name__)


class ChildToParentBM25Retriever(BaseRetriever):
    """
    将 BM25 子块检索结果升级为父块的包装器

    使用场景：
    - Parent-Child Index 模式下的 EnsembleRetriever
    - 确保 BM25 路径与 Dense 路径返回相同粒度的文档

    Metadata 约定：
    - ParentDocumentRetriever 存储子块时，会在 metadata 中添加 "doc_id" 字段
    - "doc_id" 指向 docstore 中的父块 ID
    """

    bm25_retriever: Any  # BM25Retriever 实例
    docstore: Any  # BaseStore 实例（存储父块）
    k: int = 4  # 返回的父块数量
    search_kwargs: dict = {}  # BM25 检索参数

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """
        执行检索：BM25 子块 -> 父块升级

        流程：
        1. BM25 检索子块
        2. 提取 doc_id 并去重
        3. 从 docstore 获取父块
        4. 返回父块列表
        """
        # 1. BM25 检索子块（多召回一些，因为多个子块可能指向同一父块）
        fetch_k = self.k * 3  # 召回 3 倍子块以确保足够的父块
        self.bm25_retriever.k = fetch_k

        try:
            child_docs = self.bm25_retriever.invoke(query)
        except Exception as e:
            logger.error(f"BM25 检索失败: {e}")
            return []

        if not child_docs:
            return []

        # 2. 提取 doc_id 并去重（保持顺序）
        seen_parent_ids = set()
        unique_parent_ids = []

        for doc in child_docs:
            doc_id = doc.metadata.get("doc_id")
            if doc_id and doc_id not in seen_parent_ids:
                seen_parent_ids.add(doc_id)
                unique_parent_ids.append(doc_id)

            # 达到目标数量后停止
            if len(unique_parent_ids) >= self.k:
                break

        if not unique_parent_ids:
            # 没有 doc_id，说明可能不是 Parent-Child 模式的数据
            # 降级返回子块本身
            logger.warning("子块缺少 doc_id metadata，降级返回子块")
            return child_docs[:self.k]

        # 3. 从 docstore 获取父块
        parent_docs = []
        for parent_id in unique_parent_ids:
            try:
                parent_doc = self.docstore.mget([parent_id])
                if parent_doc and parent_doc[0]:
                    parent_docs.append(parent_doc[0])
            except Exception as e:
                logger.warning(f"获取父块失败 (id={parent_id}): {e}")
                continue

        logger.info(
            f"ChildToParentBM25: {len(child_docs)} 子块 -> "
            f"{len(unique_parent_ids)} unique IDs -> {len(parent_docs)} 父块"
        )

        return parent_docs[:self.k]

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """异步版本（暂用同步实现）"""
        return self._get_relevant_documents(query, run_manager=run_manager)
