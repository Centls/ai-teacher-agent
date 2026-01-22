# -*- coding: utf-8 -*-
"""
Query Understanding 模块 - 查询理解

强依赖复用：
- instructor: 结构化输出（完整复用，不重写）
- pydantic: Schema 定义（完整复用，不重写）
- langsmith: 追踪（通过 traced 装饰器复用）

职责边界：
- 本模块仅负责 Schema 定义与调用编排
- 结构化输出由 instructor 库完整实现
- 追踪由 langsmith 库完整实现

功能：
- 实体提取：提取产品名、品牌名、功能名等
- 意图分类：判断用户查询类型
- 查询改写：将带指代的查询改写为独立完整的查询

使用方式：
    from src.services.rag.query_understanding import analyze_query, QueryAnalysis

    result = analyze_query("X100手表续航怎么样")
    print(result.entities)         # ["X100手表"]
    print(result.intent)           # "product_inquiry"
    print(result.standalone_query) # "X100手表的续航时间是多久"
"""

import logging
from typing import List, Literal, Optional

# ========== 强依赖：完整复用，不重写 ==========
from pydantic import BaseModel, Field

from src.core.instructor_client import get_instructor_client, traced, get_model_name
from config.settings import settings

logger = logging.getLogger(__name__)


# ========== Schema 定义（配置层，非逻辑实现）==========

class QueryAnalysis(BaseModel):
    """
    查询分析结果结构

    依赖：pydantic.BaseModel（完整复用）
    """

    # 实体识别
    entities: List[str] = Field(
        default_factory=list,
        description="提取的实体：产品名、品牌名、功能名、属性名等"
    )

    # 意图分类（与现有 classify_knowledge_type 对齐）
    intent: Literal[
        "product_inquiry",      # 产品咨询：问产品功能、规格、特点
        "sales_technique",      # 销售技巧：怎么卖、怎么说服客户
        "objection_handling",   # 异议处理：客户说太贵、不需要等
        "competitor_compare",   # 竞品对比：和其他产品比较
        "material_request",     # 素材请求：要文案、海报、话术
        "general_chat"          # 闲聊：与业务无关的对话
    ] = Field(
        default="product_inquiry",
        description="用户意图类型"
    )

    # 查询类型
    query_type: Literal[
        "factual",      # 事实查询：X100续航多久？
        "comparative",  # 对比查询：X100和Y200哪个好？
        "procedural",   # 流程查询：怎么处理退货？
        "opinion"       # 意见查询：这个产品值得买吗？
    ] = Field(
        default="factual",
        description="查询类型"
    )

    # 改写后的独立查询（解决指代问题）
    standalone_query: str = Field(
        description="改写为独立完整的查询语句，解决'它'、'这个'等指代问题"
    )

    # 置信度
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="分析结果的置信度 0.0-1.0"
    )


# ========== 核心函数（最小胶水代码）==========

# 系统提示词（配置层）
_ANALYSIS_SYSTEM_PROMPT = """你是一个查询分析专家。分析用户的查询，提取关键信息。

任务：
1. entities: 提取查询中的实体（产品名、品牌名、功能名、属性名）
2. intent: 判断用户意图
   - product_inquiry: 问产品功能、规格、特点
   - sales_technique: 怎么卖、怎么说服客户、销售技巧
   - objection_handling: 客户说太贵、不需要等异议处理
   - competitor_compare: 和其他产品比较
   - material_request: 要文案、海报、话术等素材
   - general_chat: 闲聊，与业务无关
3. query_type: 判断查询类型
   - factual: 事实查询（问是什么、有什么）
   - comparative: 对比查询（哪个好、比较）
   - procedural: 流程查询（怎么做、步骤）
   - opinion: 意见查询（值不值、好不好）
4. standalone_query: 将查询改写为独立完整的句子
   - 如果有"它"、"这个"、"那个"等指代，根据上下文替换为具体内容
   - 如果查询已经完整，直接返回原查询
5. confidence: 你对分析结果的置信度（0.0-1.0）

示例：
- "X100手表续航怎么样" → entities: ["X100手表", "续航"], intent: product_inquiry, query_type: factual
- "它的价格呢"（上文提到X100）→ standalone_query: "X100手表的价格是多少"
- "怎么让客户下单" → intent: sales_technique, query_type: procedural
- "你好" → intent: general_chat, confidence: 0.95
- "你是谁" → intent: general_chat, confidence: 0.9
- "谢谢" → intent: general_chat, confidence: 0.95
- "今天天气怎么样" → intent: general_chat, confidence: 0.9

重要：以下情况应判定为 general_chat（闲聊）：
- 问候语：你好、Hi、早上好、晚安等
- 身份询问：你是谁、你叫什么、你能做什么
- 感谢/告别：谢谢、再见、拜拜
- 与营销/产品/销售完全无关的日常对话
"""


@traced(name="query_understanding", run_type="chain")
def analyze_query(
    query: str,
    chat_history_summary: str = ""
) -> QueryAnalysis:
    """
    分析用户查询，提取实体、意图、改写查询

    强依赖：
    - instructor.chat.completions.create（完整复用）
    - pydantic 自动验证（完整复用）

    Args:
        query: 用户查询
        chat_history_summary: 对话历史摘要（用于解决指代问题，可选）

    Returns:
        QueryAnalysis: 结构化分析结果
    """
    client = get_instructor_client()

    # 构建用户消息
    user_content = f"用户查询：{query}"
    if chat_history_summary:
        user_content = f"对话历史摘要：{chat_history_summary}\n\n{user_content}"

    try:
        # 依赖：instructor.chat.completions.create（完整复用，不重写）
        # 依赖：pydantic 自动验证（完整复用，不重写）
        result = client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_model=QueryAnalysis,
            max_retries=2  # instructor 内置重试机制（完整复用）
        )

        logger.info(
            f"[QueryUnderstanding] Query: '{query[:30]}...' → "
            f"Intent: {result.intent}, Entities: {result.entities}"
        )

        return result

    except Exception as e:
        logger.warning(f"[QueryUnderstanding] Analysis failed: {e}, returning default")
        # 降级：返回默认结果（保证功能可用）
        return QueryAnalysis(
            entities=[],
            intent="product_inquiry",
            query_type="factual",
            standalone_query=query,
            confidence=0.0
        )


# ========== 历史摘要配置（对齐业界标准）==========
# 轮数限制：最近 3 轮对话（Human + AI）
# Token 限制：约 2000 Token（~1500 汉字）
HISTORY_MAX_TURNS = 3
HISTORY_MAX_TOKENS = 2000  # 约 1500 汉字


def create_chat_history_summary(
    messages: list,
    max_turns: int = HISTORY_MAX_TURNS,
    max_tokens: int = HISTORY_MAX_TOKENS
) -> str:
    """
    创建对话历史摘要（用于 Query Understanding）

    配置（对齐业界标准）：
    - 轮数限制：最近 3 轮（可通过 max_turns 调整）
    - Token 限制：约 2000 Token（可通过 max_tokens 调整）

    截断策略：
    1. 先取最近 N 轮对话
    2. 从最新的消息开始累加，直到达到 Token 限制
    3. 超出限制时停止添加更早的消息

    Args:
        messages: 消息列表（LangChain Message 对象）
        max_turns: 最大轮次（默认 3 轮）
        max_tokens: 最大 Token 数（默认 2000，约 1500 汉字）

    Returns:
        str: 对话历史摘要
    """
    if not messages:
        return ""

    # 取最近 N 轮（每轮 = 1 Human + 1 AI = 2 条消息）
    recent = messages[-max_turns * 2:] if len(messages) > max_turns * 2 else messages

    summary_parts = []
    total_chars = 0
    # 估算：1 Token ≈ 0.75 汉字，2000 Token ≈ 1500 汉字
    max_chars = int(max_tokens * 0.75)

    for msg in recent:
        role = getattr(msg, 'type', 'unknown')
        content = getattr(msg, 'content', str(msg))

        if role == 'human':
            line = f"用户: {content}"
        elif role == 'ai':
            line = f"助手: {content}"
        else:
            continue

        # Token 限制检查：如果加上这条消息会超出限制
        if total_chars + len(line) > max_chars:
            # 计算剩余空间
            remaining = max_chars - total_chars
            if remaining > 50:  # 至少保留 50 字符才有意义
                summary_parts.append(line[:remaining] + "...")
            break

        summary_parts.append(line)
        total_chars += len(line)

    return "\n".join(summary_parts) if summary_parts else ""