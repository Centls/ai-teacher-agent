# -*- coding: utf-8 -*-
"""
Query Rewriting 模块 - 查询重写

强依赖复用 LangChain 组件，仅编写最小胶水代码：
1. 历史融合 - langchain.chains.create_history_aware_retriever（完整复用）
2. Multi-Query - langchain.retrievers.multi_query.MultiQueryRetriever（完整复用）

功能：
- 历史融合：解决多轮对话中的指代消歧问题（"它" → 具体产品名）
- Multi-Query：将用户口语化查询扩展为多个专业术语查询，提升召回率

依赖来源：
- langchain.chains.create_history_aware_retriever
- langchain.retrievers.multi_query.MultiQueryRetriever
- langchain_core.prompts.ChatPromptTemplate
- langchain_core.prompts.MessagesPlaceholder
"""

import logging
from typing import List, Optional

# ========== 强依赖：LangChain 核心组件（完整复用，不重写） ==========
from langchain_classic.chains import create_history_aware_retriever
from langchain_classic.retrievers import MultiQueryRetriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.language_models import BaseLanguageModel

logger = logging.getLogger(__name__)


# ========== Prompt 模板（配置层，非逻辑实现） ==========

# 历史融合 Prompt：将带指代的问题改写为独立完整的查询
CONTEXTUALIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """根据对话历史，将用户问题改写为独立完整的查询。

规则：
1. 将"它"、"这个"、"那个"、"上面说的"等指代词替换为具体内容
2. 补充对话中提到的产品名、功能名等上下文信息
3. 如果问题已经是独立完整的，直接返回原问题
4. 只返回改写后的问题，不要任何解释或前缀

示例：
- 历史提到"X100智能手表"，问题"续航呢" → "X100智能手表的续航时间是多久"
- 历史提到"减肥产品轻盈丸"，问题"怎么卖" → "减肥产品轻盈丸怎么销售"
- 历史提到"客户说太贵"，问题"怎么回应" → "客户说产品太贵了怎么回应"
"""),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])


class QueryRewriter:
    """
    查询重写器 - 完整复用 LangChain 组件

    职责边界（遵循强依赖复用原则）：
    - 本类仅负责组合调度，不实现任何检索/改写算法
    - 历史融合算法：由 create_history_aware_retriever 完整实现
    - Multi-Query 算法：由 MultiQueryRetriever 完整实现

    使用方式：
        from src.services.rag.query_rewriter import QueryRewriter

        rewriter = QueryRewriter(base_retriever, llm)

        # 有对话历史时
        docs = rewriter.retrieve_with_history(query, chat_history)

        # 无对话历史时
        docs = rewriter.retrieve_with_multi_query(query)

        # 自动选择策略
        docs = rewriter.retrieve(query, chat_history)
    """

    def __init__(self, base_retriever: BaseRetriever, llm: BaseLanguageModel):
        """
        初始化查询重写器

        Args:
            base_retriever: 基础检索器（来自 RAGPipeline 或 MultimodalRAGPipeline）
            llm: LLM 实例（用于查询改写）
        """
        self.base_retriever = base_retriever
        self.llm = llm

        # 懒加载缓存
        self._history_aware_retriever: Optional[BaseRetriever] = None
        self._multi_query_retriever: Optional[MultiQueryRetriever] = None

        logger.info("QueryRewriter 初始化完成（历史融合 + Multi-Query）")

    @property
    def history_aware_retriever(self) -> BaseRetriever:
        """
        历史感知检索器（懒加载）

        依赖：langchain.chains.create_history_aware_retriever（完整复用）

        功能：
        - 自动分析对话历史
        - 将指代词替换为具体内容
        - 生成独立完整的查询

        Returns:
            BaseRetriever: 历史感知检索器
        """
        if self._history_aware_retriever is None:
            # 依赖：create_history_aware_retriever（完整复用，不重写）
            self._history_aware_retriever = create_history_aware_retriever(
                self.llm,
                self.base_retriever,
                CONTEXTUALIZE_PROMPT
            )
            logger.info("✅ 历史融合检索器初始化完成 (create_history_aware_retriever)")

        return self._history_aware_retriever

    @property
    def multi_query_retriever(self) -> MultiQueryRetriever:
        """
        多查询检索器（懒加载）

        依赖：langchain.retrievers.multi_query.MultiQueryRetriever（完整复用）

        功能：
        - 自动将用户查询扩展为多个变体
        - 分别检索并合并去重结果
        - 提升召回率

        Returns:
            MultiQueryRetriever: 多查询检索器
        """
        if self._multi_query_retriever is None:
            # 依赖：MultiQueryRetriever.from_llm（完整复用，不重写）
            self._multi_query_retriever = MultiQueryRetriever.from_llm(
                retriever=self.base_retriever,
                llm=self.llm
            )
            logger.info("✅ Multi-Query 检索器初始化完成 (MultiQueryRetriever)")

        return self._multi_query_retriever

    def retrieve_with_history(
        self,
        query: str,
        chat_history: List[BaseMessage]
    ) -> List:
        """
        带历史上下文的检索（历史融合）

        适用场景：多轮对话，需要解决指代消歧

        Args:
            query: 用户当前问题
            chat_history: 对话历史（LangChain Message 列表）

        Returns:
            List[Document]: 检索到的文档列表
        """
        logger.info(f"[QueryRewriter] 历史融合检索: '{query[:50]}...' (历史: {len(chat_history)} 条)")

        # 依赖：history_aware_retriever.invoke（完整复用）
        return self.history_aware_retriever.invoke({
            "input": query,
            "chat_history": chat_history
        })

    def retrieve_with_multi_query(self, query: str) -> List:
        """
        多查询扩展检索（Multi-Query）

        适用场景：首轮对话，用户口语化表达

        Args:
            query: 用户问题

        Returns:
            List[Document]: 检索到的文档列表（多查询合并去重后）
        """
        logger.info(f"[QueryRewriter] Multi-Query 检索: '{query[:50]}...'")

        # 依赖：multi_query_retriever.invoke（完整复用）
        return self.multi_query_retriever.invoke(query)

    def retrieve(
        self,
        query: str,
        chat_history: Optional[List[BaseMessage]] = None
    ) -> List:
        """
        智能检索：自动选择最优策略

        策略选择：
        - 有对话历史 → 历史融合（解决指代消歧）
        - 无对话历史 → Multi-Query（提升首轮召回）

        Args:
            query: 用户问题
            chat_history: 对话历史（可选）

        Returns:
            List[Document]: 检索到的文档列表
        """
        if chat_history and len(chat_history) > 0:
            return self.retrieve_with_history(query, chat_history)
        else:
            return self.retrieve_with_multi_query(query)


def create_query_rewriter(base_retriever: BaseRetriever, llm: BaseLanguageModel) -> QueryRewriter:
    """
    工厂函数：创建 QueryRewriter 实例

    Args:
        base_retriever: 基础检索器
        llm: LLM 实例

    Returns:
        QueryRewriter: 查询重写器实例
    """
    return QueryRewriter(base_retriever, llm)