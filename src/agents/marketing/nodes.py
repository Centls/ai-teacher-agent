"""
AI 营销老师 - CRAG 节点实现 (White-box Reuse)

复用来源: Agentic-RAG-Ollama/scripts/nodes.py
适配:
1. 替换 ChatOllama 为 DeepSeek (OpenAI Compatible)
2. 替换金融 Prompt 为营销 Prompt
3. 集成项目内部 RAGPipeline
"""

from typing import List, Annotated, Dict, Any, Optional, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from pydantic import BaseModel, Field
import operator
import os
from langgraph.types import interrupt
from openai import OpenAI
import instructor

from src.agents.marketing.llm import llm  # 使用项目统一配置的 DeepSeek LLM
from src.services.rag.multimodal_pipeline import MultimodalRAGPipeline  # 统一使用多模态 Pipeline
from src.services.rag.query_rewriter import QueryRewriter  # Query Rewriting（历史融合 + Multi-Query）
from src.services.rag.query_understanding import analyze_query, create_chat_history_summary  # Query Understanding（Instructor）
from src.agents.marketing.learning import reflect_on_feedback
from langgraph.store.base import BaseStore
from config.settings import settings


def keep_latest(current: Any, new: Any) -> Any:
    """
    Reducer that keeps the latest (newest) value, used for flag fields.
    Handles initial state where current might be None.
    """
    if new is not None:
        return new
    if current is not None:
        return current
    return False  # Default for bool fields

# =============================================================================
# Web Search Tools (White-box Reuse: langchain_community)
# 复用来源: menonpg/agentic_search_openai_langgraph
# =============================================================================
from langchain_community.tools import DuckDuckGoSearchResults

# =============================================================================
# State 定义
# =============================================================================

class MarketingState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    question: str
    retrieved_docs: str  # 最终合并后的文档（用于生成）
    kb_docs: str  # 知识库检索的文档
    web_docs: str  # Web 搜索的文档
    rewritten_queries: List[str]
    generation: str
    grade: str  # 'yes', 'partial', 'no' - 添加 partial 用于补充混合
    hallucination_grade: str # 'yes' or 'no'
    answer_grade: str # 'yes' or 'no'
    retry_count: int
    user_feedback: Optional[str]
    source_type: Literal["knowledge_base", "web_search", "hybrid", "fallback"]  # 添加 hybrid 类型
    force_web_search: Annotated[bool, keep_latest]  # 使用 reducer 确保值被正确传递
    skip_hitl: Annotated[bool, keep_latest]  # 拒绝后跳过人工审批

# =============================================================================
# Pydantic Schemas (复用自 Agentic-RAG)
# =============================================================================

class GradeDocuments(BaseModel):
    """Relevance score for retrieved documents."""
    relevance_score: str = Field(
        description="Document relevance: 'yes' (highly relevant), 'partial' (somewhat relevant, may need supplement), 'no' (not relevant)"
    )

class GradeHallucinations(BaseModel):
    """Binary score for hallucination present in generation answer."""
    binary_score: str = Field(description="Answer is grounded with the facts for the query, 'yes' or 'no'")

class GradeAnswer(BaseModel):
    """Binary score to assess answer addresses query."""
    binary_score: str = Field(description="Answer addresses the query, 'yes' or 'no'")

class SearchQueries(BaseModel):
    """Search queries for retrieving missing information."""
    search_queries: list[str] = Field(description="1-3 search queries to retrieve the missing information.")


class KnowledgeTypeClassification(BaseModel):
    """
    知识类型分类结果
    复用项目 LLM 进行意图分类，决定检索哪个知识子库
    """
    knowledge_type: str = Field(
        description="Knowledge type: 'product_raw' (product features/specs), 'sales_raw' (sales skills/objection handling), 'material' (copywriting/marketing materials), 'conclusion' (best practices/conclusions), 'all' (search all types)"
    )
    reasoning: str = Field(description="Brief reasoning for this classification")


# =============================================================================
# 知识类型定义 (与 server.py 保持一致)
# =============================================================================
KNOWLEDGE_TYPES = {
    "product_raw": "产品原始资料",
    "sales_raw": "销售经验/话术",
    "material": "文案/素材",
    "conclusion": "结论型知识",
}

# =============================================================================
# Helper Functions
# =============================================================================

def get_latest_user_query(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content
    return messages[0].content if messages else ''


# ========== Schema 定义（知识分类）==========
class KnowledgeClassification(BaseModel):
    """知识类型分类结果"""
    knowledge_type: Literal["product_raw", "sales_raw", "material", "conclusion", "all"] = Field(
        description="知识类型: product_raw(产品资料), sales_raw(销售话术), material(文案素材), conclusion(结论知识), all(综合)"
    )


# 知识分类系统提示词（配置层）
_CLASSIFY_SYSTEM_PROMPT = """你是一个营销知识分类专家。根据用户问题，判断应该检索哪种类型的知识库。

知识库类型：
- product_raw: 产品功能、规格、特性、技术参数等产品原始资料
- sales_raw: 销售技巧、话术、客户异议处理、成交策略等销售经验
- material: 宣传文案、营销素材、广告语、推广内容等
- conclusion: 最佳实践、策略总结、方法论、结论性知识
- all: 问题涉及多个类型，需要综合检索

分类原则：
1. 问产品是什么、有什么功能 → product_raw
2. 问怎么卖、怎么说服客户、怎么处理异议 → sales_raw
3. 需要文案、素材、宣传内容 → material
4. 问最佳实践、策略建议、方法论 → conclusion
5. 问题模糊或涉及多方面 → all"""


def classify_knowledge_type(question: str) -> str:
    """
    使用 Instructor + LLM 分类用户问题所需的知识类型

    强依赖复用：
    - instructor: 结构化输出（完整复用，不重写）
    - langsmith: 追踪（通过 traced 装饰器复用）

    Returns:
        str: 知识类型 ('product_raw', 'sales_raw', 'material', 'conclusion', 'all')
    """
    # 使用统一 Instructor Client（带 LangSmith 追踪）
    from src.core.instructor_client import get_instructor_client, traced, get_model_name

    @traced(name="classify_knowledge_type", run_type="chain")
    def _classify(q: str) -> str:
        client = get_instructor_client()

        # 依赖：instructor.chat.completions.create（完整复用，不重写）
        result = client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": f"用户问题: {q}"}
            ],
            response_model=KnowledgeClassification,
            max_retries=2  # instructor 内置重试机制（完整复用）
        )
        return result.knowledge_type

    try:
        result = _classify(question)
        print(f"[CLASSIFY/Instructor] Question: '{question[:50]}...' -> Type: {result}")
        return result

    except Exception as e:
        print(f"[CLASSIFY/Instructor] Error: {e}, fallback to 'all'")
        return "all"

def detect_web_search_intent(question: str) -> bool:
    """
    检测用户是否明确请求进行 Web 搜索（联网搜索）

    注意：仅当用户明确表示要进行"联网"/"网络"搜索时才返回 True
    普通的"搜索xxx"应该使用知识库检索，而非 Web 搜索
    """
    # 明确的联网搜索关键词（必须包含"联网"、"网络"、"互联网"等词）
    explicit_web_keywords = [
        "联网搜索", "网络搜索", "在线搜索", "搜索网上", "搜索互联网",
        "web search", "search online", "search the web", "internet search",
        "查一下网上", "去网上找", "上网查", "百度一下", "谷歌一下",
        "帮我联网", "用网络", "从网上"
    ]

    # 时效性关键词（表示需要最新信息）
    realtime_keywords = [
        "最新", "实时", "当前", "今天的新闻", "最近的新闻",
        "latest news", "current news", "real-time", "today's"
    ]

    question_lower = question.lower()

    # 检查明确的联网搜索意图
    if any(keyword in question_lower for keyword in explicit_web_keywords):
        return True

    # 检查时效性意图（但需要更严格的匹配）
    if any(keyword in question_lower for keyword in realtime_keywords):
        return True

    return False

# =============================================================================
# Nodes 实现 (Adapted)
# =============================================================================

def retrieve_node(state: MarketingState) -> Dict[str, Any]:
    """
    检索节点: 从知识库检索相关文档
    支持:
    1. 前端开关控制的 Web 搜索 (force_web_search 直接传入)
    2. 智能意图检测 (仅作为后备)
    3. 按知识类型分类检索 (knowledge_type filter)
    4. Query Understanding（Instructor 实现，提取实体/意图/改写查询）
    5. Query Rewriting（历史融合 + Multi-Query）

    强依赖复用：
    - instructor: Query Understanding 结构化输出（完整复用）
    - langsmith: 追踪（完整复用）
    - langchain.chains.create_history_aware_retriever（历史融合）
    - langchain.retrievers.multi_query.MultiQueryRetriever（多查询扩展）
    """
    print("[RETRIEVE] Fetching documents...")

    # 获取问题
    question = state.get("question")
    if not question:
        question = get_latest_user_query(state.get("messages", []))

    # 获取对话历史（用于历史融合）
    messages = state.get("messages", [])

    # ========== Query Understanding（Instructor 实现）==========
    # 强依赖：instructor + langsmith（完整复用）
    # 功能：提取实体、判断意图、改写查询
    query_entities = []
    query_intent = None
    try:
        # 创建对话历史摘要（用于解决指代问题）
        history_summary = create_chat_history_summary(messages, max_turns=3)

        # 调用 Query Understanding（带 LangSmith 追踪）
        qu_result = analyze_query(question, history_summary)

        query_entities = qu_result.entities
        query_intent = qu_result.intent

        # 如果 Query Understanding 改写了查询，使用改写后的查询
        if qu_result.standalone_query and qu_result.standalone_query != question:
            print(f"[QU] Query rewritten: '{question[:30]}...' -> '{qu_result.standalone_query[:30]}...'")
            question = qu_result.standalone_query

        print(f"[QU] Entities: {query_entities}, Intent: {query_intent}, Confidence: {qu_result.confidence:.2f}")
    except Exception as e:
        print(f"[QU] Query Understanding failed: {e}, continuing with original query")

    # 检查前端开关是否已启用 Web 搜索
    force_web_search = state.get("force_web_search", False)

    # 如果前端未开启，才检测意图（作为后备）
    if not force_web_search:
        force_web_search = detect_web_search_intent(question)

    # 分类问题类型，决定检索哪个知识子库
    knowledge_type = classify_knowledge_type(question)
    metadata_filter = None if knowledge_type == "all" else {"knowledge_type": knowledge_type}
    print(f"[RETRIEVE] Knowledge type: {knowledge_type}, filter: {metadata_filter}")

    if force_web_search:
        print(f"[RETRIEVE] Web search mode enabled for: '{question}'")

        # 智能混合模式：先尝试从知识库检索
        pipeline = MultimodalRAGPipeline()
        try:
            docs = pipeline.retrieve(question, k=3, metadata_filter=metadata_filter)

            if docs and any(d.page_content.strip() for d in docs):
                # 知识库有相关内容 → 触发混合模式
                print(f"[RETRIEVE] Found {len(docs)} KB docs, triggering hybrid mode")

                # 格式化知识库文档
                doc_texts = []
                for i, d in enumerate(docs, 1):
                    source_name = d.metadata.get('original_filename', 'Unknown Source')
                    doc_texts.append(f"[Source {i}] (File: {source_name}):\n{d.page_content}")

                kb_content = "\n\n".join(doc_texts)
                kb_formatted = f"## Query: {question}\n\n### Retrieved Documents:\n{kb_content}"

                return {
                    'retrieved_docs': kb_formatted,
                    'kb_docs': kb_formatted,
                    'question': question,
                    'force_web_search': True,
                    'grade': 'partial'  # 触发混合搜索
                }
            else:
                # 知识库无相关内容 → 纯 Web 搜索
                print("[RETRIEVE] No relevant KB docs, triggering pure web search")
                return {
                    'retrieved_docs': '',
                    'kb_docs': '',
                    'question': question,
                    'force_web_search': True,
                    'grade': 'no'  # 触发纯 Web 搜索
                }
        except Exception as e:
            print(f"[RETRIEVE] KB search error: {e}, fallback to pure web search")
            return {
                'retrieved_docs': '',
                'kb_docs': '',
                'question': question,
                'force_web_search': True,
                'grade': 'no'
            }

    rewritten_queries = state.get('rewritten_queries', [])
    queries_to_search = rewritten_queries if rewritten_queries else [question]

    # 详细日志：显示将要使用的查询
    print(f"[RETRIEVE] rewritten_queries from state: {rewritten_queries}")
    print(f"[RETRIEVE] queries_to_search: {queries_to_search}")

    # 初始化多模态 RAG Pipeline
    pipeline = MultimodalRAGPipeline()

    # ========== Query Rewriting（历史融合 + Multi-Query）==========
    # 依赖：QueryRewriter（内部复用 LangChain 组件）
    # - 有对话历史 → 历史融合（解决指代消歧）
    # - 无对话历史 → Multi-Query（提升首轮召回）
    #
    # 历史截断配置（对齐业界标准）：
    # - 轮数限制：最近 3 轮（6 条消息：3 Human + 3 AI）
    # - Token 限制：约 2000 Token（~1500 汉字）
    REWRITER_MAX_TURNS = 3
    REWRITER_MAX_TOKENS = 2000  # 约 1500 汉字

    all_history = [m for m in messages[:-1] if isinstance(m, BaseMessage)] if len(messages) > 1 else []
    # 截断到最近 N 轮（每轮 = 1 Human + 1 AI = 2 条消息）
    recent_history = all_history[-(REWRITER_MAX_TURNS * 2):] if len(all_history) > REWRITER_MAX_TURNS * 2 else all_history

    # Token 限制：截断超出限制的消息内容
    max_chars = int(REWRITER_MAX_TOKENS * 0.75)  # 1 Token ≈ 0.75 汉字
    total_chars = 0
    chat_history = []

    for msg in recent_history:
        content = getattr(msg, 'content', '')
        content_len = len(content) if content else 0

        if total_chars + content_len > max_chars:
            # 超出限制，截断当前消息或停止添加
            remaining = max_chars - total_chars
            if remaining > 50:  # 至少保留 50 字符才有意义
                truncated_content = content[:remaining] + "..."
                # 保持消息类型
                if isinstance(msg, HumanMessage):
                    chat_history.append(HumanMessage(content=truncated_content))
                elif isinstance(msg, AIMessage):
                    chat_history.append(AIMessage(content=truncated_content))
            break

        chat_history.append(msg)
        total_chars += content_len

    # 判断是否启用 Query Rewriting（首次检索时启用，重试时使用 rewritten_queries）
    use_query_rewriting = not rewritten_queries  # 没有重写查询时才使用 Query Rewriting

    if use_query_rewriting:
        try:
            # 创建 QueryRewriter（复用 LangChain 组件）
            query_rewriter = QueryRewriter(
                base_retriever=pipeline.vectorstore.as_retriever(search_kwargs={"k": 3, "filter": metadata_filter}),
                llm=llm
            )

            # 使用 Query Rewriting 检索
            print(f"[RETRIEVE] Using QueryRewriter (history: {len(chat_history)} messages)")
            docs = query_rewriter.retrieve(question, chat_history if chat_history else None)

            if docs:
                # 格式化文档内容
                doc_texts = []
                for i, d in enumerate(docs, 1):
                    source_name = d.metadata.get('original_filename', 'Unknown Source')
                    doc_texts.append(f"[Source {i}] (File: {source_name}):\n{d.page_content}")

                combined_result = f"## Query: {question}\n\n### Retrieved Documents:\n" + "\n\n".join(doc_texts)

                return {
                    'retrieved_docs': combined_result,
                    'kb_docs': combined_result,
                    'question': question,
                    'source_type': 'knowledge_base'
                }
        except Exception as e:
            print(f"[RETRIEVE] QueryRewriter failed: {e}, fallback to direct retrieval")
            # 降级到直接检索

    # ========== 降级/重试：直接检索模式 ==========
    all_results = []
    for idx, search_query in enumerate(queries_to_search, 1):
        print(f"[RETRIEVE] Query {idx}: {search_query}")

        # Extract keywords for BM25 Re-ranking (Simple strategy: split by space, filter short words)
        # In a full implementation, we might use an LLM to extract keywords, but this is efficient.
        keywords = [w for w in search_query.split() if len(w) > 2]

        # 使用 MultimodalRAGPipeline 进行检索 (Hybrid Search with Re-ranking + Knowledge Type Filter)
        docs = pipeline.retrieve(search_query, k=3, keywords=keywords, metadata_filter=metadata_filter)

        # 格式化文档内容 with Source IDs for citation
        doc_texts = []
        for i, d in enumerate(docs, 1):
            source_name = d.metadata.get('original_filename', 'Unknown Source')
            doc_texts.append(f"[Source {i}] (File: {source_name}):\n{d.page_content}")

        doc_txt = "\n\n".join(doc_texts)
        text = f"## Query {idx}: {search_query}\n\n### Retrieved Documents:\n{doc_txt}"
        all_results.append(text)

    combined_result = "\n\n".join(all_results)

    return {
        'retrieved_docs': combined_result,
        'kb_docs': combined_result,  # 同时存储到 kb_docs
        'question': question,
        'source_type': 'knowledge_base'
    }

def grade_documents_node(state: MarketingState) -> Dict[str, Any]:
    """
    文档评估节点: 判断检索到的文档是否与问题相关 (Marketing Context)
    支持三级评分: yes (完全相关), partial (部分相关，需要补充), no (不相关)
    """
    print("[GRADE] Evaluating document relevance")

    # 检查是否已经由 retrieve_node 设置了 grade (智能混合模式)
    existing_grade = state.get("grade")
    if existing_grade == "partial":
        # retrieve_node 已判断为混合模式，直接保持
        print("[GRADE] Using pre-set grade from retrieve_node: partial (hybrid mode)")
        return {'grade': 'partial'}

    # 如果用户明确请求 Web 搜索且 grade='no'，保持 force_web_search 标志
    force_web_search = state.get("force_web_search", False)
    if force_web_search and existing_grade == "no":
        print("[GRADE] Skipping - User explicitly requested web search (pure mode)")
        return {'grade': 'no', 'force_web_search': True}

    question = state.get("question")
    documents = state.get('retrieved_docs', '')

    if not documents:
        return {'grade': 'no'}

    llm_structured = llm.with_structured_output(GradeDocuments)

    # 更新后的 Prompt 支持三级评分
    # NOTE: 阿里云 API 要求使用 json_object response_format 时，消息中必须包含 "json" 关键词
    # NOTE: 必须在 prompt 中明确指定 JSON 字段名，否则 LLM 可能返回不匹配的字段名
    system_prompt = """You are a senior marketing strategist assessing the relevance of retrieved documents to a user's marketing question.

GRADING SCALE:
- 'yes': Documents are HIGHLY relevant and contain sufficient information to fully answer the query
- 'partial': Documents are SOMEWHAT relevant but may need supplementation with additional information (e.g., missing recent data, incomplete coverage)
- 'no': Documents are NOT relevant to the query at all

GUIDELINES:
- If documents contain core marketing concepts directly related to the query → 'yes'
- If documents are tangentially related or cover only part of the query → 'partial'
- If documents are completely unrelated to marketing or the specific query → 'no'

You MUST respond with a JSON object containing EXACTLY this field:
{"relevance_score": "<yes|partial|no>"}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Retrieved Document: {documents}\n\nUser query: {question}")
    ]

    try:
        response = llm_structured.invoke(messages)
        grade = response.relevance_score.lower()
        # 标准化输出
        if grade not in ['yes', 'partial', 'no']:
            grade = 'yes' if 'yes' in grade else ('partial' if 'partial' in grade else 'no')
    except Exception as e:
        print(f"[GRADE] Error: {e}")
        grade = "yes"  # Fallback

    print(f"[GRADE] Relevance: {grade}")

    if grade == 'yes':
        return {'grade': 'yes'}
    elif grade == 'partial':
        # 部分相关：保留知识库文档，触发补充搜索
        return {'grade': 'partial'}
    else:
        return {'grade': 'no', 'retrieved_docs': ''}  # Clear docs if irrelevant

def _format_docs_summary(documents: str, max_chars_per_doc: int = 100) -> str:
    """
    将检索文档格式化为摘要形式：每条显示标题 + 前 N 字符

    Args:
        documents: 原始检索文档字符串
        max_chars_per_doc: 每条文档内容的最大字符数

    Returns:
        格式化后的摘要字符串
    """
    if not documents:
        return "无相关文档"

    # 解析文档格式: [Source X] (File: xxx):\n内容
    import re
    pattern = r'\[(?:Source|Web Source)\s*(\d+)\]\s*(?:\(File:\s*([^)]+)\)|([^\n]+))[:：]?\n?(.*?)(?=\[(?:Source|Web Source)\s*\d+\]|$)'
    matches = re.findall(pattern, documents, re.DOTALL)

    if not matches:
        # 无法解析，返回截断的原始内容
        return documents[:500] + "..." if len(documents) > 500 else documents

    summaries = []
    for match in matches:
        source_num = match[0]
        file_name = match[1] if match[1] else match[2]  # File name or title
        content = match[3].strip()

        # 截取内容摘要
        content_preview = content[:max_chars_per_doc]
        if len(content) > max_chars_per_doc:
            content_preview += "..."

        # 格式化摘要
        if file_name:
            summaries.append(f"[{source_num}] 📄 {file_name.strip()}\n   {content_preview}")
        else:
            summaries.append(f"[{source_num}] {content_preview}")

    # 添加统计信息
    total_docs = len(summaries)
    header = f"共检索到 {total_docs} 条文档：\n\n"

    return header + "\n\n".join(summaries)


def human_approval_node(state: MarketingState) -> Dict[str, Any]:
    """
    HITL Approval Node: Interrupts execution to request user approval.
    传递上下文信息给用户审核，包括数据来源类型

    如果 skip_hitl 为 True（拒绝后重试），则跳过中断直接返回
    """
    # 获取当前状态的调试信息
    skip_hitl = state.get("skip_hitl", False)
    retry_count = state.get("retry_count", 0)
    print(f"[HITL] Entering human_approval_node - skip_hitl={skip_hitl}, retry_count={retry_count}")

    # 检查是否跳过人工审批（拒绝后重试场景）
    if skip_hitl:
        print(f"[HITL] Skipping approval (skip_hitl=True, retry_count={retry_count})")
        # 重置 skip_hitl 标志，并自动批准
        return {"user_feedback": "approved", "skip_hitl": False}

    print("[HITL] Requesting human approval")

    question = state.get("question", "")
    documents = state.get("retrieved_docs", "")
    source_type = state.get("source_type", "unknown")

    # 根据来源类型生成不同的审核消息
    source_labels = {
        "knowledge_base": "📚 知识库",
        "web_search": "🌐 Web 搜索",
        "hybrid": "📚+🌐 混合来源（知识库 + Web 补充）",
        "fallback": "⚠️ 备用"
    }
    source_label = source_labels.get(source_type, source_type)

    # 生成文档摘要（每条显示标题 + 前 100 字）
    docs_summary = _format_docs_summary(documents, max_chars_per_doc=100)

    # 传递审核上下文给前端
    review_context = {
        "question": question,
        "retrieved_docs": docs_summary,  # 使用摘要格式
        "source_type": source_type,
        "source_label": source_label,
        "message": f"数据来源: {source_label}\n请审核检索到的内容是否相关，确认后将基于这些内容生成回答。"
    }

    # Interrupt execution and wait for user input
    user_input = interrupt(review_context)

    print(f"[HITL] User input: {user_input}")

    return {"user_feedback": user_input}

async def learning_node(state: MarketingState, store: BaseStore) -> Dict[str, Any]:
    """
    学习节点: 分析用户反馈并更新偏好规则
    """
    print("[LEARNING] Analyzing feedback...")
    
    feedback = state.get("user_feedback")
    messages = state.get("messages")
    
    if not feedback:
        return {}
        
    # Get current rules
    namespace = ("marketing_preferences",)
    key = "user_rules"
    
    # Note: store.aget returns an Item or None
    current_rules_item = await store.aget(namespace, key)
    current_rules = current_rules_item.value["rules"] if current_rules_item and "rules" in current_rules_item.value else "*no rules yet*"
    
    # Reflect
    new_rules = await reflect_on_feedback(messages, current_rules)
    
    # Update store
    await store.aput(namespace, key, {"rules": new_rules})
    
    print(f"[LEARNING] Updated Rules: {new_rules}")
    
    return {}

async def generate_node(state: MarketingState, store: BaseStore) -> Dict[str, Any]:
    """
    生成节点: 基于文档生成营销建议 (Marketing Context)
    支持 Fallback: 无相关文档时使用通用回答
    """
    print("[GENERATE] Creating Answer")

    question = state.get("question")
    documents = state.get('retrieved_docs', '')
    retry_count = state.get("retry_count", 0)

    # Get user rules
    namespace = ("marketing_preferences",)
    key = "user_rules"
    current_rules_item = await store.aget(namespace, key)
    user_rules = current_rules_item.value["rules"] if current_rules_item and "rules" in current_rules_item.value else "*no rules yet*"

    # 检查是否有相关文档
    has_documents = bool(documents and documents.strip())

    if has_documents:
        # 正常模式: 基于文档生成
        system_prompt = """You are an expert AI Marketing Consultant providing actionable, strategic advice.

    USER PREFERENCES:
    {user_rules}

    OUTPUT FORMAT:
    Write a comprehensive, engaging answer (200-300 words) in MARKDOWN format:
    - Use ## headings for key strategies
    - Use **bold** for emphasis
    - Use bullet points for actionable steps
    - Include inline citations like [1], [2] where applicable

    GUIDELINES:
    - Base your advice ONLY on the provided documents, but synthesize them into a coherent strategy.
    - Focus on marketing metrics (ROI, conversion, engagement) rather than just financial data.
    - Be practical and solution-oriented.
    - Use professional marketing terminology.

    CITATIONS:
    At the end, list references in this format:
    **References:**
    1. Source: [Document Name/Snippet]"""

        system_prompt = system_prompt.format(user_rules=user_rules)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Retrieved Document: {documents}\n\nUser query: {question}")
        ]
    else:
        # Fallback 模式: 没有相关文档，使用通用回答
        print(f"[GENERATE] Fallback mode - No relevant documents (retry_count: {retry_count})")
        system_prompt = """You are an AI Marketing Consultant.

The user's question doesn't seem to have relevant documents in our marketing knowledge base.

INSTRUCTIONS:
- If it's a general question (like "who are you"), introduce yourself as an AI Marketing teacher/consultant.
- If it's a marketing question we don't have docs for, provide general marketing principles and suggest the user upload relevant materials.
- Be helpful and friendly.
- Keep the response concise (100-150 words).
- Use MARKDOWN format.

USER PREFERENCES:
{user_rules}"""

        system_prompt = system_prompt.format(user_rules=user_rules)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"User query: {question}")
        ]

    response = await llm.ainvoke(messages)
    generation = response.content

    return {
        'generation': generation,
        'messages': [AIMessage(content=generation)]
    }

def transform_query_node(state: MarketingState) -> Dict[str, Any]:
    """
    查询重写节点: 将复杂问题拆解为具体的营销搜索查询 (Marketing Context)
    """
    print("[TRANSFORM] Rewriting query")

    question = state.get("question")
    rewritten_queries = state.get('rewritten_queries', [])
    current_retry = state.get("retry_count", 0)
    retry_count = current_retry + 1  # 增加重试计数

    print(f"[TRANSFORM] Original question: '{question}'")
    print(f"[TRANSFORM] Previous rewritten_queries: {rewritten_queries}")
    print(f"[TRANSFORM] Current retry_count in state: {current_retry}, new retry_count: {retry_count}")

    llm_structured = llm.with_structured_output(SearchQueries)

    # Adapted Prompt for Marketing
    # NOTE: 阿里云 API 要求使用 json_object response_format 时，消息中必须包含 "json" 关键词
    # NOTE: 必须在 prompt 中明确指定 JSON 字段名，否则 LLM 可能返回不匹配的字段名
    system_prompt = """You are a marketing research assistant that decomposes complex marketing questions into focused search queries.

DECOMPOSITION STRATEGY:
Break down the original query into 1-3 specific, focused queries targeting:
- Specific marketing channels (e.g., "SEO trends 2024", "Social media benchmarks")
- Target audience segments
- Competitor strategies
- Specific metrics (e.g., "CAC benchmarks", "Retention rates")

GUIDELINES:
- Expand marketing acronyms (e.g., "PPC" -> "Pay-per-click")
- Add marketing context if missing
- Make each query self-contained and specific
- Keep queries concise

CRITICAL RULE - YOU MUST FOLLOW THIS:
If previous queries are provided below, you MUST generate COMPLETELY DIFFERENT queries.
Do NOT repeat any previous query, even with minor word changes.
Try alternative angles, different keywords, or focus on different aspects of the topic.

EXAMPLES:
- "How to improve ROI on Facebook Ads?" ->
["Facebook Ads ROI optimization strategies", "Facebook advertising benchmarks 2024"]

You MUST respond with a JSON object containing EXACTLY this field:
{"search_queries": ["query1", "query2", ...]}"""

    query_context = f"Original Query: {question}"
    if rewritten_queries:
        query_context += f"""

⚠️ IMPORTANT: The following queries have ALREADY been tried and returned unsatisfactory results.
You MUST generate COMPLETELY NEW and DIFFERENT queries. Do NOT repeat these:

Previous Failed Queries:
"""
        for idx, q in enumerate(rewritten_queries, 1):
            query_context += f"{idx}. {q}\n"

        query_context += f"""
Generate NEW queries that:
- Use different keywords and phrases
- Explore different aspects of the topic
- Try alternative search angles (e.g., case studies, best practices, step-by-step guides)
- Consider related but distinct topics

Retry attempt: {retry_count}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query_context)
    ]

    response = llm_structured.invoke(messages)
    new_queries = response.search_queries

    print(f"[TRANSFORM] New Queries: {new_queries} (retry: {retry_count})")

    # 代码层面检测重复查询（备用机制）
    # 如果 LLM 生成的查询与之前完全相同，使用备用策略
    if rewritten_queries and new_queries:
        # 计算重复率
        overlap_count = sum(1 for q in new_queries if q in rewritten_queries)
        overlap_ratio = overlap_count / len(new_queries) if new_queries else 0

        if overlap_ratio > 0.5:  # 超过 50% 重复
            print(f"[TRANSFORM] WARNING: {overlap_ratio*100:.0f}% queries are duplicates, using fallback strategy")

            # 动态后缀策略：根据问题类型选择相关后缀
            knowledge_type = classify_knowledge_type(question)
            print(f"[TRANSFORM] Detected knowledge type: {knowledge_type}")

            # 按知识类型定义后缀（更贴合知识库内容）
            type_specific_suffixes = {
                "product_raw": [
                    "产品功能详解",
                    "技术参数说明",
                    "产品优势对比",
                    "核心卖点分析",
                    "使用场景介绍",
                    "产品原理解析"
                ],
                "sales_raw": [
                    "客户异议处理",
                    "成交话术技巧",
                    "销售沟通方法",
                    "客户需求挖掘",
                    "促单策略",
                    "销售实战经验"
                ],
                "material": [
                    "文案模板参考",
                    "营销素材示例",
                    "推广内容创意",
                    "宣传文案写法",
                    "广告语设计",
                    "内容营销案例"
                ],
                "conclusion": [
                    "最佳实践总结",
                    "策略方法论",
                    "经验教训分析",
                    "关键成功因素",
                    "执行要点归纳",
                    "核心结论提炼"
                ],
                "all": [
                    "综合解决方案",
                    "全面分析报告",
                    "系统性指南",
                    "完整方法论",
                    "整体策略规划",
                    "多维度分析"
                ]
            }

            # 根据知识类型选择后缀策略
            if knowledge_type == "all":
                # 综合性问题：生成 4 个查询，覆盖全部知识类型
                all_types = ["product_raw", "sales_raw", "material", "conclusion"]

                new_queries = []
                question_short = question[:35]  # 综合查询用更短的前缀（4个查询）
                for t in all_types:
                    # 每次重试使用不同的后缀索引
                    suffix_index = (retry_count - 1) % len(type_specific_suffixes[t])
                    suffix = type_specific_suffixes[t][suffix_index]
                    new_queries.append(f"{question_short} {suffix}")

                print(f"[TRANSFORM] Fallback queries (综合, 全类型覆盖, retry={retry_count}): {new_queries}")
            else:
                # 单一类型：使用对应后缀
                fallback_suffixes = type_specific_suffixes.get(knowledge_type, type_specific_suffixes["all"])

                # 根据重试次数选择不同的后缀
                suffix_index = (retry_count - 1) % len(fallback_suffixes)
                fallback_query = f"{question[:50]} {fallback_suffixes[suffix_index]}"

                new_queries = [fallback_query]
                print(f"[TRANSFORM] Fallback query (type={knowledge_type}): {new_queries}")

    # 根据重试次数决定是否跳过审批
    # retry_count >= 3 时自动生成，不再显示审批卡片
    max_retries_before_auto = 3
    skip_approval = retry_count >= max_retries_before_auto

    if skip_approval:
        print(f"[TRANSFORM] Max retries ({max_retries_before_auto}) reached, will auto-generate")

    return {
        "rewritten_queries": new_queries,
        "retry_count": retry_count,  # 返回更新后的重试计数
        "skip_hitl": skip_approval  # 超过3次自动生成，否则再次审批
    }

def check_answer_quality(state: MarketingState) -> Dict[str, Any]:
    """
    幻觉检测与质量评估节点
    """
    print("[CHECK] Checking answer quality")
    
    question = state.get("question")
    documents = state.get('retrieved_docs', '')
    generation = state.get("generation")

    # 1. Hallucination Check
    llm_hallucinations = llm.with_structured_output(GradeHallucinations)

    # NOTE: 阿里云 API 要求使用 json_object response_format 时，消息中必须包含 "json" 关键词
    # NOTE: 必须在 prompt 中明确指定 JSON 字段名，否则 LLM 可能返回不匹配的字段名
    hallucination_prompt = """You are a grader assessing whether an LLM generation is grounded in / supported by a set of retrieved facts.
Give a binary score 'yes' or 'no'. 'Yes' means that the answer is grounded in / supported by the set of facts.

You MUST respond with a JSON object containing EXACTLY this field:
{"binary_score": "<yes|no>"}"""

    messages = [
        SystemMessage(content=hallucination_prompt),
        HumanMessage(content=f"Set of facts:\n\n{documents}\n\nLLM Generation: {generation}")
    ]
    
    try:
        res_hallucination = llm_hallucinations.invoke(messages)
        hallucination_grade = res_hallucination.binary_score
    except:
        hallucination_grade = "yes"

    print(f"[CHECK] Hallucination Grade: {hallucination_grade}")

    if hallucination_grade == 'yes':
        # 2. Answer Quality Check
        llm_answer = llm.with_structured_output(GradeAnswer)

        # NOTE: 阿里云 API 要求使用 json_object response_format 时，消息中必须包含 "json" 关键词
        # NOTE: 必须在 prompt 中明确指定 JSON 字段名，否则 LLM 可能返回不匹配的字段名
        answer_prompt = """You are a grader assessing whether an answer addresses / resolves a query.
Give a binary score 'yes' or 'no'. 'Yes' means that the answer resolves the query.

You MUST respond with a JSON object containing EXACTLY this field:
{"binary_score": "<yes|no>"}"""
        
        messages = [
            SystemMessage(content=answer_prompt),
            HumanMessage(content=f"User Query: {question}\n\n LLM Generation: {generation}")
        ]
        
        try:
            res_answer = llm_answer.invoke(messages)
            answer_grade = res_answer.binary_score
        except:
            answer_grade = "yes"
            
        print(f"[CHECK] Answer Grade: {answer_grade}")
        
        return {
            "hallucination_grade": hallucination_grade,
            "answer_grade": answer_grade
        }
    else:
        return {
            "hallucination_grade": hallucination_grade,
            "answer_grade": "no"
        }

# =============================================================================
# Web Search Node (White-box Reuse)
# 复用来源: menonpg/agentic_search_openai_langgraph, psykick-21/deep-research
# =============================================================================

def web_search_node(state: MarketingState) -> Dict[str, Any]:
    """
    Web Search 节点: 支持两种模式
    1. 纯 Web 搜索: 当知识库完全不相关时
    2. 补充混合: 当知识库部分相关时，合并两个来源

    复用策略:
    - 直接复用 langchain_community.tools.DuckDuckGoSearchResults
    - 支持可选的 Tavily (需要 API Key)
    """
    # 增加重试计数（Web 搜索也计入重试次数）
    current_retry = state.get("retry_count", 0)
    retry_count = current_retry + 1
    print(f"[WEB_SEARCH] Initiating web search... (retry_count: {current_retry} -> {retry_count})")

    question = state.get("question", "")
    rewritten_queries = state.get("rewritten_queries", [])
    kb_docs = state.get("kb_docs", "")  # 获取已有的知识库文档
    current_grade = state.get("grade", "no")

    # 调试信息
    print(f"[WEB_SEARCH] Current grade: {current_grade}")
    print(f"[WEB_SEARCH] KB docs available: {bool(kb_docs and kb_docs.strip())}")
    if kb_docs:
        print(f"[WEB_SEARCH] KB docs preview: {kb_docs[:200]}...")

    # 使用重写后的查询或原始问题
    search_query = rewritten_queries[-1] if rewritten_queries else question

    # 初始化搜索工具 (White-box Reuse: langchain_community)
    use_tavily = settings.USE_TAVILY and settings.TAVILY_API_KEY

    try:
        if use_tavily:
            from langchain_community.tools.tavily_search import TavilySearchResults
            search_tool = TavilySearchResults(
                max_results=5,
                search_depth="advanced",
                include_answer=True
            )
            print("[WEB_SEARCH] Using Tavily Search API")
        else:
            search_tool = DuckDuckGoSearchResults(
                max_results=5,
                output_format="list"
            )
            print("[WEB_SEARCH] Using DuckDuckGo Search")

        # 执行搜索
        results = search_tool.invoke(search_query)

        # 格式化搜索结果
        if isinstance(results, list):
            web_docs = []
            for i, r in enumerate(results, 1):
                if isinstance(r, dict):
                    title = r.get("title", "Untitled")
                    snippet = r.get("snippet", r.get("body", r.get("content", "")))
                    link = r.get("link", r.get("url", ""))
                    web_docs.append(f"[Web Source {i}] {title}\n{snippet}\nURL: {link}")
                else:
                    web_docs.append(f"[Web Source {i}] {str(r)}")
            web_results = "\n\n".join(web_docs)
        else:
            web_results = str(results)

        print(f"[WEB_SEARCH] Retrieved {len(results) if isinstance(results, list) else 1} results")

        # 决定是混合模式还是纯 Web 模式
        if current_grade == "partial" and kb_docs:
            # 补充混合模式: 合并知识库和 Web 结果
            print("[WEB_SEARCH] Hybrid mode - Merging KB docs with Web results")
            combined_docs = f"""## Knowledge Base Documents (Internal Sources)

{kb_docs}

---

## Web Search Supplement for: {search_query}

{web_results}"""
            source_type = "hybrid"
        else:
            # 纯 Web 模式
            combined_docs = f"## Web Search Results for: {search_query}\n\n{web_results}"
            source_type = "web_search"

        # 根据重试次数决定是否跳过审批（与 transform_query_node 逻辑一致）
        max_retries_before_auto = 3
        skip_approval = retry_count >= max_retries_before_auto

        if skip_approval:
            print(f"[WEB_SEARCH] Max retries ({max_retries_before_auto}) reached, will auto-generate")

        return {
            "retrieved_docs": combined_docs,
            "web_docs": web_results,
            "source_type": source_type,
            "grade": "yes",  # 搜索完成，可以进入生成
            "retry_count": retry_count,  # 更新重试计数
            "skip_hitl": skip_approval  # 超过3次自动生成
        }

    except Exception as e:
        print(f"[WEB_SEARCH] Error: {e}")
        # 如果 Web 搜索失败但有知识库文档，仍然使用知识库
        if kb_docs:
            return {
                "retrieved_docs": kb_docs,
                "source_type": "knowledge_base",
                "grade": "yes"
            }
        return {
            "retrieved_docs": f"Web search failed: {str(e)}",
            "source_type": "fallback",
            "grade": "yes"
        }

# =============================================================================
# Routers
# =============================================================================

def check_approval(state: MarketingState) -> str:
    """
    路由: 检查用户是否批准生成

    用户反馈选项:
    - "approved": 批准 -> 生成回答
    - "rejected": 拒绝 -> 重新检索（transform_query）
    - "web_search": 拒绝并使用 Web 搜索 -> 直接进行 Web 搜索
    """
    feedback = state.get("user_feedback")
    if feedback == "approved":
        print("[ROUTER] User approved -> Generate")
        return "generate"
    elif feedback == "web_search":
        print("[ROUTER] User requested Web Search -> Web Search")
        return "web_search"
    else:
        print("[ROUTER] User rejected -> Transform Query")
        return "transform_query"

def should_generate(state: MarketingState) -> str:
    """
    路由: 决定是生成回答、重写查询还是触发 Web 搜索

    策略 (CRAG + Web Search Fallback + 补充混合):
    - force_web_search == True -> 直接进行 Web 搜索
    - grade == 'yes' -> 直接生成
    - grade == 'partial' -> 补充 Web 搜索（混合模式）
    - retry_count >= 2 -> 触发 Web 搜索
    - 否则 -> 重写查询
    """
    grade = state.get("grade")
    retry_count = state.get("retry_count", 0)
    force_web_search = state.get("force_web_search", False)
    max_retries_before_web = 2  # 2次知识库重试后触发 Web 搜索
    max_retries = 3  # 最大重试次数

    # 用户明确请求 Web 搜索
    if force_web_search:
        print("[ROUTER] User explicitly requested Web Search -> Web Search")
        return "web_search"

    if grade == "yes":
        print("[ROUTER] Documents relevant -> Generate")
        return "generate"
    elif grade == "partial":
        # 部分相关：触发补充 Web 搜索（混合模式）
        print("[ROUTER] Documents partially relevant -> Supplement with Web Search (Hybrid)")
        return "web_search"
    elif retry_count >= max_retries_before_web and retry_count < max_retries:
        print(f"[ROUTER] KB retries exhausted ({retry_count}) -> Web Search")
        return "web_search"
    elif retry_count >= max_retries:
        print(f"[ROUTER] Max retries ({max_retries}) reached -> Force Generate (Fallback)")
        return "generate"  # 超过重试次数，强制进入生成阶段
    else:
        print(f"[ROUTER] Documents irrelevant (retry {retry_count + 1}/{max_retries}) -> Transform Query")
        return "transform_query"

def check_hallucination_router(state: MarketingState) -> str:
    """
    路由: 决定是结束、重写查询还是重新生成
    添加重试限制，防止无限循环
    """
    hallucination_grade = state.get("hallucination_grade")
    answer_grade = state.get("answer_grade")
    retry_count = state.get("retry_count", 0)
    max_retries = 3  # 最大重试次数

    if hallucination_grade == "yes":
        if answer_grade == "yes":
            print("[ROUTER] Answer is good -> END")
            return "useful"  # Map to learning node in graph
        elif retry_count >= max_retries:
            print(f"[ROUTER] Max retries ({max_retries}) reached -> Force END (Fallback)")
            return "useful"  # 超过重试次数，强制结束
        else:
            print(f"[ROUTER] Answer not useful (retry {retry_count}/{max_retries}) -> Transform Query")
            return "not useful"
    else:
        if retry_count >= max_retries:
            print(f"[ROUTER] Hallucination detected but max retries reached -> Force END")
            return "useful"  # 超过重试次数，强制结束
        print("[ROUTER] Hallucination detected -> Not Supported")
        return "not supported"
