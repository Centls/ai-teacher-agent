from typing import Literal
from src.core.state_mgr import NexusState

from src.core.prd_mgr import PRDManager

def router_node(state: NexusState) -> Literal["marketing_teacher", "training_teacher", "__end__"]:
    """
    Simple keyword based router for demo.
    In real app, use LLM classification.
    """
    # Inject System PRD Constraints (Simulation)
    # In a real app, this would be done by a dedicated "Context Loader" node before the router.
    # For now, we inject it here.
    system_constraints = PRDManager.get_system_constraints()
    marketing_constraints = PRDManager.load("marketing_prd")
    
    prd_context = {
        "system": system_constraints,
        "marketing": marketing_constraints
    }
    
    last_message = state["messages"][-1]["content"].lower()
    
    # Update state with PRD context
    state["prd_context"] = prd_context
    
    # LangGraph Router should return the next node name
    # But we also want to update the state. 
    # In this simple setup, we can't easily update state in a conditional edge function.
    # So we will rely on the fact that 'state' is mutable or use a dedicated node for context loading.
    # However, since we are in a conditional edge, we can't mutate state effectively for the next node if it's a pure function.
    # BUT, we can return the node name, and let the next node read from a global or singleton if needed, OR
    # we can change the graph to have a "context_loader" node before the router.
    
    # For this specific task constraint "not modify architecture", we will try to mutate the state dict directly
    # assuming it's passed by reference, although LangGraph might copy it.
    # A better approach for LangGraph is to return a Command, but that requires LangGraph v0.2+.
    # Let's assume standard behavior: Conditional edges are for routing.
    
    # WORKAROUND: We will use a "context_loader" pattern by just returning the node name,
    # and the nodes themselves will load the PRD using PRDManager directly (which we already implemented as a fallback/singleton).
    # Wait, I previously updated nodes to read from state.
    # Let's revert to returning just the string, and update the nodes to load from PRDManager if state is missing it,
    # OR we can try to return a Command if supported.
    
    # Let's try the simplest fix: The router function in LangGraph (conditional_edge) is expected to return a destination.
    # It cannot update state.
    # So we must move the "PRD Injection" logic to a proper Node, OR rely on the nodes to load it themselves.
    # Since I already updated nodes to read from state['prd_context'], I should probably update them to fallback to PRDManager.load()
    # if the key is missing.
    
    # However, the prompt asked to "Inject PRDContext into Global State".
    # To do this properly in LangGraph, we need a Node.
    # But I cannot change the graph structure easily (as per "No architecture changes").
    # So, I will modify the 'supervisor_node' (which IS a node) to do the injection!
    
    # Dynamic Routing based on Capability Registry
    from src.core.registry import TeacherRegistry
    
    registry = TeacherRegistry.get_instance()
    
    # Simple heuristic: Check if user explicitly asks for a task supported by a teacher
    # In a real system, this would be an LLM call using the descriptions from the registry
    
    capable_teacher = registry.find_capable_teacher(last_message, prd_context)
    
    if capable_teacher:
        print(f"--- Supervisor: Routing to {capable_teacher} (Capability Match) ---")
        return f"{capable_teacher}_teacher"
        
    print("--- Supervisor: No capable teacher found (Refusal) ---")
    return "refusal_node"
