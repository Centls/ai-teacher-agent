import yaml
from pathlib import Path
from langchain_core.output_parsers import JsonOutputParser
from src.core.llm_provider import get_llm_provider
from src.core.status import ExecutionStatus, ReasonCode
from .state import SupportState

llm_provider = get_llm_provider()

def load_boundaries():
    path = Path(__file__).parent / "boundaries.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def boundary_check_node(state: SupportState):
    print("--- Support: Boundary Check ---")
    user_request = state["messages"][-1]["content"].lower()
    boundaries = load_boundaries()
    
    # Simple keyword check for demo
    for prohibited in boundaries.get("prohibited_topics", []):
        # Check both "medical_advice" and "medical advice"
        if prohibited in user_request or prohibited.replace("_", " ") in user_request:
            return {
                "boundary_check_result": "FAIL",
                "status": "REFUSAL",
                "messages": [{"role": "assistant", "content": f"I cannot answer questions about {prohibited}."}],
                "execution_result": {
                    "status": ExecutionStatus.REFUSED,
                    "reason_code": ReasonCode.PRD_VIOLATION,
                    "message": f"Prohibited topic: {prohibited}",
                    "result": None,
                    "diagnostics": {"topic": prohibited},
                    "retryable": False
                }
            }
            
    return {
        "boundary_check_result": "PASS",
        "execution_result": {
            "status": ExecutionStatus.SUCCESS,
            "reason_code": ReasonCode.NONE,
            "message": "Boundary check passed",
            "result": None,
            "diagnostics": None,
            "retryable": False
        }
    }

def answer_node(state: SupportState):
    print("--- Support: Answering ---")
    if state.get("boundary_check_result") == "FAIL":
        return {}

    user_request = state["messages"][-1]["content"]
    
    # Mock LLM Call
    template = "You are a support agent. Answer: {question}"
    context = {"question": user_request}
    
    # Use Provider
    result = llm_provider.invoke(template, context, output_parser=JsonOutputParser())
    
    # Check if refund is needed (Mock logic)
    tool_result = None
    if "refund" in user_request.lower():
        from src.core.tools.registry import ToolRegistry
        try:
            tool_registry = ToolRegistry.get_instance()
            print("--- Support: Requesting Refund Tool ---")
            tool_result = tool_registry.request_execution(
                teacher_name="support",
                tool_name="refund_tool",
                kwargs={"user_id": "user_123", "amount": 50.0, "reason": "customer request"},
                dry_run=False
            )
            result["tool_output"] = tool_result
        except Exception as e:
            print(f"--- Support: Tool Execution Failed: {e} ---")
            tool_result = {"error": str(e)}

    return {
        "solution": result.get("solution"),
        "issue_category": result.get("issue_category"),
        "messages": [{"role": "assistant", "content": result.get("answer", "I can help with that.") + (f" [Tool Result: {tool_result}]" if tool_result else "")}],
        "execution_result": {
            "status": ExecutionStatus.SUCCESS,
            "reason_code": ReasonCode.NONE,
            "message": "Answer generated",
            "result": result,
            "diagnostics": {"tool_result": tool_result},
            "retryable": False
        }
    }

def confidence_review_node(state: SupportState):
    print("--- Support: Confidence Review ---")
    if state.get("boundary_check_result") == "FAIL":
        return {}
        
    # Mock Confidence
    return {
        "confidence_score": 0.95,
        "status": "SUCCESS",
        "execution_result": {
            "status": ExecutionStatus.SUCCESS,
            "reason_code": ReasonCode.NONE,
            "message": "Review passed",
            "result": {"score": 0.95},
            "diagnostics": None,
            "retryable": False
        }
    }
