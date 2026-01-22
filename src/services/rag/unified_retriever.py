"""
统一检索器 (UnifiedRetriever) - 纯编排器

设计原则：复用现有组件，不重复实现任何算法

复用的组件：
1. RAGPipeline._ensemble_retrieve → RRF 融合 (EnsembleRetriever)
2. RAGPipeline.reranker → Cross-Encoder 重排序
3. RAGPipeline.parent_retriever → 父子索引 (ParentDocumentRetriever)
4. QueryRewriter → 历史融合 + Multi-Query (LangChain 组件)

本模块仅负责：
- 编排调用顺序
- 合并多查询结果
- 去重（基于 doc_id）
- 配置漏斗参数

漏斗模型：粗召回 → 去重 → Cross-Encoder 精排 → Top-K
"""

import logging
import hashlib
from typing import List, Optional
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


class UnifiedRetriever:
    """
    统一检索器 - 编排现有 RAG 组件形成完整链路

    链路：
    Query Understanding (已在 nodes.py 完成)
        ↓
    Query Variants (来自 state 或 Multi-Query)
        ↓
    粗召回：EnsembleRetriever (Dense + BM25 RRF 融合)
        ↓
    去重：基于 doc_id / content hash
        ↓
    精排：Cross-Encoder 统一重排序
        ↓
    Top-K 返回
    """

    def __init__(
        self,
        pipeline,
        llm=None,
        coarse_fetch_k: int = 50,
        rerank_max_candidates: int = 100,
        final_top_k: int = 10,
    ):
        """
        初始化统一检索器

        Args:
            pipeline: RAGPipeline/MultimodalRAGPipeline 实例（复用其内部组件）
            llm: LLM 实例（用于 QueryRewriter，可选）
            coarse_fetch_k: 每个查询变体的粗召回数量
            rerank_max_candidates: Cross-Encoder 最大输入候选数
            final_top_k: 最终返回文档数
        """
        self.pipeline = pipeline
        self.llm = llm
        self.coarse_fetch_k = coarse_fetch_k
        self.rerank_max_candidates = rerank_max_candidates
        self.final_top_k = final_top_k

        logger.info(
            f"✅ UnifiedRetriever 初始化 (编排器): "
            f"coarse_k={coarse_fetch_k}, max_candidates={rerank_max_candidates}, top_k={final_top_k}"
        )

    def retrieve(
        self,
        query: str,
        query_variants: Optional[List[str]] = None,
        metadata_filter: Optional[dict] = None,
        top_k: Optional[int] = None,
    ) -> List[Document]:
        """
        统一检索：编排漏斗模型

        Args:
            query: 原始用户查询（用于 Cross-Encoder 重排序）
            query_variants: 查询变体列表（来自 Query Understanding 或 Multi-Query）
            metadata_filter: 元数据过滤条件
            top_k: 最终返回数量

        Returns:
            排序后的文档列表
        """
        final_k = top_k or self.final_top_k
        queries = query_variants if query_variants else [query]

        print(f"[UnifiedRetriever] 开始检索，查询变体数: {len(queries)}")  # 确保控制台可见
        logger.info(f"[UnifiedRetriever] 开始检索，查询变体数: {len(queries)}")

        # ========== 1. 粗召回：复用 Pipeline._ensemble_retrieve ==========
        all_candidates: List[Document] = []
        use_parent_child = self.pipeline.parent_retriever is not None

        for i, q in enumerate(queries, 1):
            try:
                # 复用 Pipeline 的 EnsembleRetriever（RRF 融合）
                docs = self.pipeline._ensemble_retrieve(
                    query=q,
                    fetch_k=self.coarse_fetch_k,
                    use_parent_child=use_parent_child,
                    metadata_filter=metadata_filter
                )
                all_candidates.extend(docs)
                logger.info(f"[UnifiedRetriever] 查询 {i}/{len(queries)} 召回 {len(docs)} 文档")
            except Exception as e:
                logger.warning(f"[UnifiedRetriever] 查询 {i} 失败: {e}，尝试降级")
                try:
                    docs = self.pipeline._fallback_dense_retrieve(
                        query=q,
                        fetch_k=self.coarse_fetch_k,
                        use_parent_child=use_parent_child,
                        metadata_filter=metadata_filter
                    )
                    all_candidates.extend(docs)
                except Exception as e2:
                    logger.error(f"[UnifiedRetriever] 降级也失败: {e2}")

        if not all_candidates:
            logger.warning("[UnifiedRetriever] 未召回任何文档")
            return []

        total_recalled = len(all_candidates)
        logger.info(f"[UnifiedRetriever] 粗召回完成: {total_recalled} 文档")

        # ========== 2. 去重：基于 doc_id（父子索引）或 content hash ==========
        deduped_docs = self._deduplicate(all_candidates)
        logger.info(f"[UnifiedRetriever] 去重: {total_recalled} -> {len(deduped_docs)} 文档")

        # 限制进入 Cross-Encoder 的候选数
        candidates_for_rerank = deduped_docs[:self.rerank_max_candidates]

        # ========== 3. 精排：复用 Pipeline.reranker (Cross-Encoder) ==========
        reranker = self.pipeline.reranker

        if reranker is not None and len(candidates_for_rerank) > 0:
            try:
                # 使用原始查询进行重排序（语义最准确）
                pairs = [[query, doc.page_content] for doc in candidates_for_rerank]
                scores = reranker.predict(pairs)

                # 按分数降序排列
                ranked = sorted(zip(candidates_for_rerank, scores), key=lambda x: x[1], reverse=True)
                results = [doc for doc, _ in ranked[:final_k]]

                if ranked:
                    top_score = ranked[0][1]
                    bottom_score = ranked[min(final_k - 1, len(ranked) - 1)][1]
                    logger.info(
                        f"[UnifiedRetriever] Cross-Encoder 精排: {len(candidates_for_rerank)} -> {len(results)} 文档 "
                        f"(分数范围: {bottom_score:.3f} ~ {top_score:.3f})"
                    )

                return results

            except Exception as e:
                logger.warning(f"[UnifiedRetriever] Cross-Encoder 失败: {e}，返回去重结果")

        # 降级：无 Cross-Encoder，直接返回去重后的 Top-K
        logger.info(f"[UnifiedRetriever] 无 Cross-Encoder，返回前 {final_k} 文档")
        return deduped_docs[:final_k]

    def _deduplicate(self, docs: List[Document]) -> List[Document]:
        """
        文档去重：基于 doc_id（父子索引模式）或 content hash

        保留首次出现的文档（通常排名更高）
        """
        seen_ids: set = set()
        unique_docs: List[Document] = []

        for doc in docs:
            # 优先使用 doc_id（Parent-Child 模式的父块 ID）
            doc_id = doc.metadata.get('doc_id')

            if doc_id:
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_docs.append(doc)
            else:
                # 降级：使用 content hash
                content_hash = hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()[:16]
                if content_hash not in seen_ids:
                    seen_ids.add(content_hash)
                    unique_docs.append(doc)

        return unique_docs

    def retrieve_with_query_expansion(
        self,
        query: str,
        chat_history: Optional[List[BaseMessage]] = None,
        metadata_filter: Optional[dict] = None,
        top_k: Optional[int] = None,
        num_variants: int = 3,
    ) -> tuple[List[Document], List[str]]:
        """
        带查询扩展的检索 - 复用 QueryRewriter

        当没有预生成的查询变体时，使用此方法

        Args:
            query: 原始用户查询
            chat_history: 对话历史
            metadata_filter: 元数据过滤
            top_k: 最终返回数量
            num_variants: 查询变体数量

        Returns:
            (文档列表, 查询变体列表)
        """
        if self.llm is None:
            # 无 LLM，使用单查询
            logger.info("[UnifiedRetriever] 无 LLM，使用原始查询")
            docs = self.retrieve(query=query, query_variants=[query], metadata_filter=metadata_filter, top_k=top_k)
            return docs, [query]

        try:
            # 复用 QueryRewriter 生成查询变体
            from src.services.rag.query_rewriter import QueryRewriter

            # 创建临时 retriever（仅用于 Multi-Query 生成变体，不用于实际检索）
            # 使用 k=1 最小化资源消耗
            temp_retriever = self.pipeline.vectorstore.as_retriever(search_kwargs={"k": 1})

            query_rewriter = QueryRewriter(
                base_retriever=temp_retriever,
                llm=self.llm
            )

            # 获取 Multi-Query 生成的变体
            # 注意：这里我们只使用 MultiQueryRetriever 的查询生成能力
            multi_query_retriever = query_rewriter.multi_query_retriever

            # 生成查询变体（复用 LangChain 的 generate_queries）
            variants = multi_query_retriever.generate_queries(query, run_manager=None)

            # 确保包含原始查询
            if query not in variants:
                variants = [query] + list(variants)

            # 限制变体数量
            variants = variants[:num_variants + 1]

            logger.info(f"[UnifiedRetriever] Multi-Query 生成 {len(variants)} 个查询变体")

        except Exception as e:
            logger.warning(f"[UnifiedRetriever] 查询扩展失败: {e}，使用原始查询")
            variants = [query]

        # 使用变体执行统一检索
        docs = self.retrieve(query=query, query_variants=variants, metadata_filter=metadata_filter, top_k=top_k)

        return docs, variants