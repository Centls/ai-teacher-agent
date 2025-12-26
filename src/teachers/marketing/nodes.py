import json
from langchain_core.output_parsers import JsonOutputParser
from src.core.prompt_mgr import PromptManager
from src.core.prd_mgr import PRDManager
from src.core.llm_provider import get_llm_provider
from src.core.status import ExecutionStatus, ReasonCode
from .state import MarketingState

# Initialize LLM Provider
llm_provider = get_llm_provider()

def plan_node(state: MarketingState):
    print("--- Marketing: Planning ---")
    
    try:
        # Load PRD from State (Injected by Supervisor)
        prd_context = state.get("prd_context", {})
        marketing_prd = prd_context.get("marketing", {})
        
        # Load Prompt
        prompt_data = PromptManager.load("teachers/marketing/latest")
        template = prompt_data["plan"]["instructions"]
        
        # Get User Request
        user_request = state["messages"][-1]["content"]
        
        # Context with PRD
        context = {
            "user_request": user_request,
            "prd_constraints": marketing_prd
        }
        
        # Use Provider
        result = llm_provider.invoke(template, context, output_parser=JsonOutputParser())
        print(f"[DEBUG] Plan Result: {result}")
        
        # Simulate RAG Hit (In real app, this comes from RAG service)
        rag_hit = True 
        
        # Store in scratchpad to ensure persistence across subgraph
        return {
            "scratchpad": {
                "target_audience": result.get("target_audience"),
                "product_description": result.get("product_description"),
                "marketing_plan": result.get("marketing_goal"),
                "rag_hit": rag_hit # Persist RAG status
            },
            "execution_result": {
                "status": ExecutionStatus.SUCCESS,
                "reason_code": ReasonCode.NONE,
                "message": "Planning completed successfully",
                "result": result,
                "diagnostics": {"rag_hit": rag_hit},
                "retryable": False
            }
        }
    except Exception as e:
        print(f"Planning Error: {e}")
        return {
            "error": str(e),
            "execution_result": {
                "status": ExecutionStatus.FAILED,
                "reason_code": ReasonCode.SYSTEM_ERROR,
                "message": str(e),
                "result": None,
                "diagnostics": {"error": str(e)},
                "retryable": True
            }
        }

def execute_node(state: MarketingState):
    print("--- Marketing: Executing ---")
    
    try:
        scratchpad = state.get("scratchpad", {})
        print(f"[DEBUG] Execute Scratchpad: {scratchpad}")
        
        # Load PRD from State
        prd_context = state.get("prd_context", {})
        marketing_prd = prd_context.get("marketing", {})
        
        # Load Prompt
        prompt_data = PromptManager.load("teachers/marketing/latest")
        template = prompt_data["execute"]["instructions"]
        
        # Context
        context = {
            "target_audience": scratchpad.get("target_audience", "General Audience"),
            "product_description": scratchpad.get("product_description", "Generic Product"),
            "marketing_goal": scratchpad.get("marketing_plan", "Increase Awareness"),
            "prd_constraints": marketing_prd
        }
        
        # Use Provider
        result = llm_provider.invoke(template, context, output_parser=JsonOutputParser())
        try:
            print(f"[DEBUG] Execute Result: {repr(result)}")
        except:
            pass
        
        # Tool Call Simulation
        from src.core.tools.registry import ToolRegistry
        try:
            tool_registry = ToolRegistry.get_instance()
            print("--- Marketing: Requesting Publish Tool ---")
            # Note: We are calling 'publish_tool' which is allowed for marketing
            tool_output = tool_registry.request_execution(
                teacher_name="marketing",
                tool_name="publish_tool",
                kwargs={"platform": "RedNote", "content": "Promo Content"},
                dry_run=True # Use dry run for safety
            )
            result["tool_output"] = tool_output
        except Exception as e:
            print(f"--- Marketing: Tool Execution Failed: {e} ---")
            result["tool_error"] = str(e)
        
        return {
            "scratchpad": {
                "channel_strategy": result.get("channel_strategy"),
                "content_plan": result.get("content_plan"),
                "core_positioning": result.get("core_positioning")
            },
            "execution_result": {
                "status": ExecutionStatus.SUCCESS,
                "reason_code": ReasonCode.NONE,
                "message": "Execution completed successfully",
                "result": result,
                "diagnostics": None,
                "retryable": False
            }
        }
    except Exception as e:
        print(f"Execution Error: {e}")
        return {
            "error": str(e),
            "execution_result": {
                "status": ExecutionStatus.FAILED,
                "reason_code": ReasonCode.SYSTEM_ERROR,
                "message": str(e),
                "result": None,
                "diagnostics": {"error": str(e)},
                "retryable": True
            }
        }

def review_node(state: MarketingState):
    print("--- Marketing: Reviewing ---")
    
    try:
        scratchpad = state.get("scratchpad", {})
        
        # Load PRD from State
        prd_context = state.get("prd_context", {})
        marketing_prd = prd_context.get("marketing", {})
        
        # Load Prompt
        prompt_data = PromptManager.load("teachers/marketing/latest")
        template = prompt_data["review"]["instructions"]
        
        # Prepare Plan Summary for Review
        plan_summary = json.dumps({
            "target_audience": scratchpad.get("target_audience"),
            "strategy": scratchpad.get("channel_strategy"),
            "content_sample": scratchpad.get("content_plan")[:3] if scratchpad.get("content_plan") else []
        }, indent=2, ensure_ascii=False)
        
        # Context
        context = {
            "marketing_plan": plan_summary,
            "prd_constraints": marketing_prd,
            "user_request": state["messages"][-1]["content"] # Pass for mock logic
        }
        
        # Use Provider
        result = llm_provider.invoke(template, context, output_parser=JsonOutputParser())
        
        quality_score = result.get("quality_score", 0)
        feedback = result.get("feedback", "")
        
        # Check for PRD Violations (Simulated logic, in real app LLM decides)
        # If score is too low, we mark as REFUSED or PARTIAL_SUCCESS
        status = ExecutionStatus.SUCCESS
        reason = ReasonCode.NONE
        
        if quality_score < 60:
             status = ExecutionStatus.REFUSED
             reason = ReasonCode.PRD_VIOLATION
        elif quality_score < 80:
             status = ExecutionStatus.PARTIAL_SUCCESS
             reason = ReasonCode.MISSING_INFO
        
        # Format Final Output
        final_output = f"""
# Marketing Plan (PRD Compliant)

## Core Positioning
{scratchpad.get("core_positioning", "N/A")}

## Target Audience
{scratchpad.get("target_audience")}

## Channel Strategy
"""
        strategies = scratchpad.get("channel_strategy", {})
        if strategies:
            for channel, strat in strategies.items():
                final_output += f"- **{channel}**: {strat}\n"
        
        final_output += "\n## Content Plan Examples\n"
        content_plan = scratchpad.get("content_plan", [])
        if content_plan:
            for item in content_plan:
                final_output += f"- [{item['channel']}] {item['content']}\n"
        
        final_output += f"\n## Review\n- Quality Score: {quality_score}\n- Feedback: {feedback}\n- PRD Compliance: {status.value}"
        
        # Construct Structured Payload (The Product)
        structured_payload = {
            "core_positioning": scratchpad.get("core_positioning"),
            "target_audience": scratchpad.get("target_audience"),
            "channel_strategy": scratchpad.get("channel_strategy"),
            "content_plan": scratchpad.get("content_plan"),
            "review_feedback": {
                "score": quality_score,
                "feedback": feedback
            }
        }
        
        # Audit Flags
        rag_hit = scratchpad.get("rag_hit", False)
        hitl_triggered = False # Future: Check if HITL was requested
        
        return {
            "status": status.value,
            "quality_score": quality_score,
            "messages": [{"role": "assistant", "content": final_output}],
            "prd_compliance": status.value,
            "execution_result": {
                "status": status,
                "reason_code": reason,
                "message": feedback,
                "result": structured_payload, # THE ENVELOPE PAYLOAD
                "diagnostics": {
                    "score": quality_score,
                    "rag_hit": rag_hit,
                    "hitl_triggered": hitl_triggered,
                    "is_refused": status == ExecutionStatus.REFUSED
                },
                "retryable": False
            }
        }
    except Exception as e:
        print(f"Review Error: {e}")
        return {
            "error": str(e),
            "execution_result": {
                "status": ExecutionStatus.FAILED,
                "reason_code": ReasonCode.SYSTEM_ERROR,
                "message": str(e),
                "result": None,
                "diagnostics": {"error": str(e)},
                "retryable": True
            }
        }
