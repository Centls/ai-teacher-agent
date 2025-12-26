from langgraph.graph import StateGraph, END
from src.core.state_mgr import NexusState
from src.core.factory import GraphFactory
# from .router import router_node # Deprecated, logic moved to supervisor_node
from src.supervisor.reviewer import reviewer_node
from src.teachers.marketing.graph import MarketingTeacher
from src.teachers.support.graph import SupportTeacher
from src.core.prd_mgr import PRDManager
from src.core.registry import TeacherRegistry

# Initialize Teachers
marketing_teacher = MarketingTeacher().compile_graph()
support_teacher = SupportTeacher().compile_graph()

# Register Capabilities
from src.teachers.marketing.graph import MarketingTeacher as MarketingTeacherClass
from src.teachers.support.graph import SupportTeacher as SupportTeacherClass

registry = TeacherRegistry.get_instance()
registry.register(MarketingTeacherClass())
registry.register(SupportTeacherClass())

# Register Tools
from src.core.tools.registry import ToolRegistry
from src.tools.refund import REFUND_TOOL_SCHEMA, refund_func
from src.tools.publish import PUBLISH_TOOL_SCHEMA, publish_func

tool_registry = ToolRegistry.get_instance()
tool_registry.register(REFUND_TOOL_SCHEMA, refund_func)
tool_registry.register(PUBLISH_TOOL_SCHEMA, publish_func)

def supervisor_node(state: NexusState):
    print("--- Supervisor: Routing ---")
    
    # 1. Inject PRD Context
    system_constraints = PRDManager.get_system_constraints()
    user_context = state.get("user_context", {})
    prd_file = user_context.get("prd_file", "marketing_prd")
    marketing_constraints = PRDManager.load(prd_file)
    
    prd_context = {
        "system": system_constraints,
        "marketing": marketing_constraints
    }
    
    # 2. Determine Routing (Logic moved from router.py)
    last_message = state["messages"][-1]["content"].lower()
    
    # Check if we are in a RETRY loop
    correction_action = state.get("correction_action")
    if correction_action == "RETRY":
        # If retrying, we stay with the last teacher
        # But supervisor_node is usually the entry point.
        # If we loop back to supervisor, we might want to re-evaluate?
        # Actually, Reviewer should route directly to Teacher.
        # Supervisor is only for INITIAL routing.
        pass

    capable_teacher = registry.find_capable_teacher(last_message, prd_context)
    
    next_node = "refusal_node"
    if capable_teacher:
        print(f"--- Supervisor: Routing to {capable_teacher} (Capability Match) ---")
        next_node = f"{capable_teacher}_teacher"
    else:
        print("--- Supervisor: No capable teacher found (Refusal) ---")
    
    return {
        "prd_context": prd_context,
        "next_node": next_node,
        "last_teacher": next_node if next_node != "refusal_node" else None,
        "retry_count": 0, # Reset retry count on new routing
        "correction_action": None # Reset correction
    }

def refusal_node(state: NexusState):
    print("--- Supervisor: Refusing Request ---")
    from src.core.status import ExecutionStatus, ReasonCode
    return {
        "status": "REFUSED",
        "execution_result": {
            "status": ExecutionStatus.REFUSED,
            "reason_code": ReasonCode.NO_CAPABLE_AGENT,
            "message": "No capable teacher found for the request.",
            "result": None,
            "diagnostics": None,
            "retryable": False
        },
        "messages": [{"role": "assistant", "content": "I'm sorry, I don't have a teacher capable of handling that request."}]
    }

def route_to_teacher(state: NexusState):
    return state.get("next_node", "refusal_node")

def route_from_reviewer(state: NexusState):
    action = state.get("correction_action", "ACCEPT")
    if action == "RETRY":
        last_teacher = state.get("last_teacher")
        if last_teacher:
            print(f"--- Supervisor: Retrying {last_teacher} ---")
            return last_teacher
    
    return END

def create_supervisor_graph():
    workflow = StateGraph(NexusState)
    
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("marketing_teacher", marketing_teacher)
    workflow.add_node("support_teacher", support_teacher)
    workflow.add_node("refusal_node", refusal_node)
    workflow.add_node("reviewer", reviewer_node)
    
    workflow.set_entry_point("supervisor")
    
    # 1. Supervisor -> Teacher (via next_node)
    workflow.add_conditional_edges(
        "supervisor",
        route_to_teacher,
        {
            "marketing_teacher": "marketing_teacher",
            "support_teacher": "support_teacher",
            "refusal_node": "refusal_node",
            "__end__": END
        }
    )
    
    # 2. Teacher -> Reviewer (Self-Correction Loop)
    workflow.add_edge("marketing_teacher", "reviewer")
    workflow.add_edge("support_teacher", "reviewer")
    
    # 3. Reviewer -> Decision
    workflow.add_conditional_edges(
        "reviewer",
        route_from_reviewer,
        {
            "marketing_teacher": "marketing_teacher",
            "support_teacher": "support_teacher",
            END: END
        }
    )
    
    workflow.add_edge("refusal_node", END)
    
    return GraphFactory.compile(workflow)
