import os
from gpt_researcher import GPTResearcher
from src.core.status import ExecutionStatus, ReasonCode
from .state import ResearcherState

async def research_node(state: ResearcherState):
    """
    Executes deep research using GPT Researcher.
    """
    print("--- Researcher: Running GPT Researcher ---")
    messages = state.get("messages", [])
    user_request = messages[-1]["content"] if messages else ""
    
    try:
        # Initialize Researcher
        # Note: Environment variables for OPENAI_API_BASE/KEY and RETRIEVER should be set in .env
        researcher = GPTResearcher(query=user_request, report_type="research_report")
        
        # Run Research (Updated API)
        print(f"Starting research for: {user_request}")
        await researcher.conduct_research()
        report = await researcher.write_report()
        print("Research completed.")

        
        return {
            "summary": report,
            "messages": [{"role": "assistant", "content": report}],
            "execution_result": {
                "status": ExecutionStatus.SUCCESS,
                "reason_code": ReasonCode.NONE,
                "message": "Research completed",
                "result": {"report": report},
                "diagnostics": None,
                "retryable": False
            }
        }
    except Exception as e:
        print(f"Researcher Error: {e}")
        return {
            "error": str(e),
            "execution_result": {
                "status": ExecutionStatus.FAILED,
                "reason_code": ReasonCode.TOOL_ERROR,
                "message": str(e),
                "result": None,
                "diagnostics": None,
                "retryable": True
            }
        }
