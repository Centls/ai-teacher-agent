from langgraph.graph import StateGraph, END
from src.core.state_mgr import NexusState
from src.core.factory import GraphFactory
# from .router import router_node # Deprecated, logic moved to supervisor_node
from src.agents.supervisor.reviewer import reviewer_node
from src.agents.teachers.marketing.graph import MarketingTeacher
from src.agents.teachers.support.graph import SupportTeacher
from src.agents.researcher.graph import Researcher
from src.core.prd_mgr import PRDManager
from src.core.registry import TeacherRegistry

# Initialize Teachers
marketing_teacher = MarketingTeacher().compile_graph()
support_teacher = SupportTeacher().compile_graph()
researcher = Researcher().compile_graph()

# Register Capabilities
from src.agents.teachers.marketing.graph import MarketingTeacher as MarketingTeacherClass
from src.agents.teachers.support.graph import SupportTeacher as SupportTeacherClass
from src.agents.researcher.graph import Researcher as ResearcherClass

registry = TeacherRegistry.get_instance()
registry.register(MarketingTeacherClass())
registry.register(SupportTeacherClass())
registry.register(ResearcherClass())

# Register Tools
from src.core.tools.registry import ToolRegistry
from src.tools.refund import REFUND_TOOL_SCHEMA, refund_func
from src.tools.publish import PUBLISH_TOOL_SCHEMA, publish_func

tool_registry = ToolRegistry.get_instance()
tool_registry.register(REFUND_TOOL_SCHEMA, refund_func)
tool_registry.register(PUBLISH_TOOL_SCHEMA, publish_func)

from .nodes import supervisor_init, planner_node, router_node, refusal_node

def route_to_next(state: NexusState):
    return state.get("next_node", "refusal_node")

def route_from_reviewer(state: NexusState):
    action = state.get("correction_action", "ACCEPT")
    if action == "RETRY":
        last_teacher = state.get("last_teacher")
        if last_teacher:
            print(f"--- Supervisor: Retrying {last_teacher} ---")
            return last_teacher
    
    # If ACCEPT or anything else, go back to Router to check for next step
    return "supervisor_router"

def create_supervisor_graph():
    workflow = StateGraph(NexusState)
    
    # Nodes
    workflow.add_node("supervisor_init", supervisor_init)
    workflow.add_node("supervisor_planner", planner_node)
    workflow.add_node("supervisor_router", router_node)
    
    workflow.add_node("marketing_teacher", marketing_teacher)
    workflow.add_node("support_teacher", support_teacher)
    workflow.add_node("researcher_teacher", researcher)
    workflow.add_node("refusal_node", refusal_node)
    workflow.add_node("reviewer", reviewer_node)
    
    # Entry Point
    workflow.set_entry_point("supervisor_init")
    
    # Edges
    # 1. Init -> Planner
    workflow.add_edge("supervisor_init", "supervisor_planner")
    
    # 2. Planner -> Router
    workflow.add_edge("supervisor_planner", "supervisor_router")
    
    # 3. Router -> Teacher (or Reviewer/End)
    workflow.add_conditional_edges(
        "supervisor_router",
        route_to_next,
        {
            "marketing_teacher": "marketing_teacher",
            "support_teacher": "support_teacher",
            "researcher_teacher": "researcher_teacher",
            "refusal_node": "refusal_node",
            "reviewer": "reviewer", # If plan empty, go to reviewer (or END?)
            # Wait, router says: if not plan: return "reviewer"? 
            # If plan is empty, we are done. But we might want a final review?
            # Or if we just finished a step, we went Teacher -> Reviewer -> Router.
            # If Router sees empty, it means we are truly done.
            # Let's say Router returns "END" if empty?
            # In router_node code I wrote: return {"next_node": "reviewer"}
            # This implies a final review of the whole chain? 
            # But Reviewer expects execution_result.
            # If we just finished the loop, the last teacher result is there.
            # But if we loop Router -> Teacher -> Reviewer -> Router, 
            # Reviewer already ran for the last step.
            # So if Router is empty, we should END.
            # Let's change router_node to return END if empty.
            # But I can't change router_node here easily.
            # Let's map "reviewer" to END for now in the conditional edge if I want to skip final review.
            # Or let's map it to END directly.
            "reviewer": END,
            "__end__": END 
        }
    )
    
    # 4. Teacher -> Reviewer
    workflow.add_edge("marketing_teacher", "reviewer")
    workflow.add_edge("support_teacher", "reviewer")
    workflow.add_edge("researcher_teacher", "reviewer")
    
    # 5. Reviewer -> Router (Loop)
    workflow.add_conditional_edges(
        "reviewer",
        route_from_reviewer,
        {
            "marketing_teacher": "marketing_teacher", # Retry
            "support_teacher": "support_teacher",
            "researcher_teacher": "researcher_teacher",
            "supervisor_router": "supervisor_router" # Next step
        }
    )
    
    workflow.add_edge("refusal_node", END)
    
    return GraphFactory.compile(workflow)
