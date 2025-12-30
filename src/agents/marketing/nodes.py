"""
AI 营销老师 - CRAG 节点实现 (White-box Reuse)

复用来源: Agentic-RAG-Ollama/scripts/nodes.py
适配:
1. 替换 ChatOllama 为 DeepSeek (OpenAI Compatible)
2. 替换金融 Prompt 为营销 Prompt
3. 集成项目内部 RAGPipeline
"""

from typing import List, Annotated, Dict, Any, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import operator
from langgraph.types import interrupt

from src.agents.marketing.llm import llm  # 使用项目统一配置的 DeepSeek LLM
from src.services.rag.pipeline import RAGPipeline
from src.agents.marketing.learning import reflect_on_feedback
from langgraph.store.base import BaseStore

# =============================================================================
# State 定义
# =============================================================================

class MarketingState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    question: str
    retrieved_docs: str
    rewritten_queries: List[str]
    generation: str
    grade: str # 'yes' or 'no'
    hallucination_grade: str # 'yes' or 'no'
    answer_grade: str # 'yes' or 'no'
    retry_count: int
    user_feedback: Optional[str]

# =============================================================================
# Pydantic Schemas (复用自 Agentic-RAG)
# =============================================================================

class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents."""
    binary_score: str = Field(description="Documents are relevant to the query, 'yes' or 'no'")

class GradeHallucinations(BaseModel):
    """Binary score for hallucination present in generation answer."""
    binary_score: str = Field(description="Answer is grounded with the facts for the query, 'yes' or 'no'")

class GradeAnswer(BaseModel):
    """Binary score to assess answer addresses query."""
    binary_score: str = Field(description="Answer addresses the query, 'yes' or 'no'")

class SearchQueries(BaseModel):
    """Search queries for retrieving missing information."""
    search_queries: list[str] = Field(description="1-3 search queries to retrieve the missing information.")

# =============================================================================
# Helper Functions
# =============================================================================

def get_latest_user_query(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content
    return messages[0].content if messages else ''

# =============================================================================
# Nodes 实现 (Adapted)
# =============================================================================

def retrieve_node(state: MarketingState) -> Dict[str, Any]:
    """
    检索节点: 从知识库检索相关文档
    """
    print("[RETRIEVE] Fetching documents...")
    
    # 获取问题
    question = state.get("question")
    if not question:
        question = get_latest_user_query(state.get("messages", []))

    rewritten_queries = state.get('rewritten_queries', [])
    queries_to_search = rewritten_queries if rewritten_queries else [question]

    # 初始化 RAG Pipeline
    pipeline = RAGPipeline()
    
    all_results = []
    for idx, search_query in enumerate(queries_to_search, 1):
        print(f"[RETRIEVE] Query {idx}: {search_query}")
        
        # Extract keywords for BM25 Re-ranking (Simple strategy: split by space, filter short words)
        # In a full implementation, we might use an LLM to extract keywords, but this is efficient.
        keywords = [w for w in search_query.split() if len(w) > 2]
        
        # 使用 RAGPipeline 进行检索 (Hybrid Search with Re-ranking)
        docs = pipeline.retrieve(search_query, k=3, keywords=keywords)
        
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
        'question': question # 确保 state 中有 question
    }

def grade_documents_node(state: MarketingState) -> Dict[str, Any]:
    """
    文档评估节点: 判断检索到的文档是否与问题相关 (Marketing Context)
    """
    print("[GRADE] Evaluating document relevance")
    
    question = state.get("question")
    documents = state.get('retrieved_docs', '')

    if not documents:
        return {'grade': 'no'}

    llm_structured = llm.with_structured_output(GradeDocuments)

    # Adapted Prompt for Marketing
    system_prompt = """You are a senior marketing strategist assessing the relevance of retrieved documents to a user's marketing question.
    
    It does not need to be a stringent test. The goal is to filter out clearly irrelevant content.
    
    If the document contains marketing concepts, strategies, case studies, or data related to the user query, grade it as relevant.
    
    Give a binary score 'yes' or 'no' to indicate whether the document is relevant."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Retrieved Document: {documents}\n\nUser query: {question}")
    ]

    try:
        response = llm_structured.invoke(messages)
        grade = response.binary_score
    except Exception as e:
        print(f"[GRADE] Error: {e}")
        grade = "yes" # Fallback

    print(f"[GRADE] Relevance: {grade}")

    if grade == 'yes':
        return {'grade': 'yes'}
    else:
        return {'grade': 'no', 'retrieved_docs': ''} # Clear docs if irrelevant

def human_approval_node(state: MarketingState) -> Dict[str, Any]:
    """
    HITL Approval Node: Interrupts execution to request user approval.
    传递上下文信息给用户审核
    """
    print("[HITL] Requesting human approval")

    question = state.get("question", "")
    documents = state.get("retrieved_docs", "")

    # 传递审核上下文给前端
    review_context = {
        "question": question,
        "retrieved_docs": documents[:500] if documents else "无相关文档",  # 截断过长的文档
        "message": "请审核检索到的文档是否相关，确认后将基于这些文档生成回答。"
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
    retry_count = state.get("retry_count", 0) + 1  # 增加重试计数

    llm_structured = llm.with_structured_output(SearchQueries)

    # Adapted Prompt for Marketing
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

    EXAMPLES:
    - "How to improve ROI on Facebook Ads?" -> 
    ["Facebook Ads ROI optimization strategies", "Facebook advertising benchmarks 2024"]
    """

    query_context = f"Original Query: {question}"
    if rewritten_queries:
        query_context += f"\n\nThese queries have been already generated. Do not generate same queries again.\n"
        for idx, q in enumerate(rewritten_queries, 1):
            query_context += f"Query {idx}: {q}\n"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query_context)
    ]

    response = llm_structured.invoke(messages)
    new_queries = response.search_queries
    
    print(f"[TRANSFORM] New Queries: {new_queries} (retry: {retry_count})")

    return {
        "rewritten_queries": new_queries,
        "retry_count": retry_count  # 返回更新后的重试计数
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
    
    hallucination_prompt = """You are a grader assessing whether an LLM generation is grounded in / supported by a set of retrieved facts.
    Give a binary score 'yes' or 'no'. 'Yes' means that the answer is grounded in / supported by the set of facts."""

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
        
        answer_prompt = """You are a grader assessing whether an answer addresses / resolves a query.
        Give a binary score 'yes' or 'no'. 'Yes' means that the answer resolves the query."""
        
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
# Routers
# =============================================================================

def check_approval(state: MarketingState) -> str:
    """
    路由: 检查用户是否批准生成
    """
    feedback = state.get("user_feedback")
    if feedback == "approved":
        print("[ROUTER] User approved -> Generate")
        return "generate"
    else:
        print("[ROUTER] User rejected -> Transform Query")
        return "transform_query"

def should_generate(state: MarketingState) -> str:
    """
    路由: 决定是生成回答还是重写查询
    添加重试限制，防止无限循环
    """
    grade = state.get("grade")
    retry_count = state.get("retry_count", 0)
    max_retries = 3  # 最大重试次数

    if grade == "yes":
        print("[ROUTER] Documents relevant -> Generate")
        return "generate"
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
