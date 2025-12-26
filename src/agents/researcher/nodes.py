import json
from langchain_core.output_parsers import JsonOutputParser
from src.core.llm_provider import get_llm_provider
from src.core.status import ExecutionStatus, ReasonCode
from .state import ResearcherState

llm_provider = get_llm_provider()

def plan_research_node(state: ResearcherState):
    print("--- Researcher: Planning ---")
    messages = state.get("messages", [])
    user_request = messages[-1]["content"] if messages else ""
    
    # Knowledge Injection (RAG)
    knowledge_context = ""
    user_context = state.get("user_context", {})
    if user_context.get("use_knowledge", False):
        rag_type = user_context.get("rag_type", "mock")
        backend = user_context.get("knowledge_backend", "mock")
        kp = None
        
        if backend == "chroma" or rag_type == "chroma":
            try:
                from src.services.rag.chroma_service import ChromaKnowledgeProvider
                kp = ChromaKnowledgeProvider()
            except Exception as e:
                print(f"Failed to load Chroma Provider: {e}")
        elif rag_type == "vector":
            try:
                from src.services.rag.vector import VectorKnowledgeProvider
                kp = VectorKnowledgeProvider()
            except Exception as e:
                print(f"Failed to load Vector Provider: {e}")
        else:
            from src.services.rag.mock_provider import MockKnowledgeProvider
            kp = MockKnowledgeProvider()
        
        if kp:
            knowledge = kp.query(user_request)
            if knowledge and "暂无" not in knowledge:
                knowledge_context = f"Background Knowledge:\n{knowledge}\n"

    # Simple prompt to generate queries
    prompt = f"""
    You are a Research Planner.
    User Request: {user_request}
    {knowledge_context}
    
    Generate 3 specific search queries to gather information for this request.
    Return JSON: {{ "queries": ["query1", "query2", "query3"] }}
    """
    
    try:
        result = llm_provider.invoke(prompt, {}, output_parser=JsonOutputParser())
        queries = result.get("queries", [])
        print(f"--- Researcher: Generated Queries: {queries} ---")
        return {"research_plan": queries, "research_loop_count": 0}
    except Exception as e:
        print(f"Researcher Plan Error: {e}")
        return {"error": str(e)}

def execute_search_node(state: ResearcherState):
    print("--- Researcher: Searching ---")
    queries = state.get("research_plan", [])
    results = []
    
    # Mock Search Tool (Replace with real tool later)
    # In a real app, we'd use Tavily or DuckDuckGo here.
    for query in queries:
        print(f"--- Researcher: Executing Query: {query} ---")
        # Simulated Result
        results.append({
            "query": query,
            "content": f"Simulated search result for '{query}'. Contains relevant info about the topic.",
            "source": "simulated_web"
        })
        
    return {"search_results": results}

def summarize_node(state: ResearcherState):
    print("--- Researcher: Summarizing ---")
    results = state.get("search_results", [])
    user_request = state["messages"][-1]["content"]
    
    context_text = "\n\n".join([f"Query: {r['query']}\nResult: {r['content']}" for r in results])
    
    prompt = f"""
    You are a Research Assistant.
    User Request: {user_request}
    
    Search Results:
    {context_text}
    
    Summarize the findings to answer the user's request.
    Provide a comprehensive answer.
    """
    
    try:
        summary = llm_provider.invoke(prompt, {})
        # llm_provider.invoke returns dict or str depending on implementation?
        # Checking llm_provider.py would be good, but assuming it returns dict or parsed content.
        # If it returns dict, we need to extract content.
        # Let's assume it returns the content string or dict with content.
        
        content = summary if isinstance(summary, str) else summary.get("content", str(summary))
        
        return {
            "summary": content,
            "messages": [{"role": "assistant", "content": content}],
            "execution_result": {
                "status": ExecutionStatus.SUCCESS,
                "reason_code": ReasonCode.NONE,
                "message": "Research completed",
                "result": {"summary": content, "sources": results},
                "diagnostics": None,
                "retryable": False
            }
        }
    except Exception as e:
        return {"error": str(e)}
