import json
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage

from src.core.state_mgr import NexusState
from src.core.llm_provider import LLMProvider
from src.core.registry import TeacherRegistry

def planner_node(state: NexusState) -> Dict[str, Any]:
    """
    Supervisor 2.0 Planner Node.
    Analyzes user request and available capabilities to generate an execution plan.
    """
    print("--- [Supervisor] Planning Execution ---")
    
    messages = state["messages"]
    user_request = messages[-1]["content"] if messages else ""
    
    # 1. Get Available Capabilities
    registry = TeacherRegistry.get_instance()
    capabilities = registry.get_all_capabilities()
    
    # Format capabilities for prompt
    caps_desc = []
    for cap in capabilities:
        caps_desc.append(f"- {cap['name']}: {cap['description']} (Tasks: {', '.join(cap['supported_tasks'])})")
    caps_str = "\n".join(caps_desc)
    
    # 2. Construct Prompt
    system_prompt = f"""You are the Supervisor of an AI Agent System.
Your goal is to create an Execution Plan to fulfill the user's request.

Available Agents:
{caps_str}

Rules:
1. Analyze the request. If it requires multiple steps (e.g. research then marketing), create a multi-step plan.
2. If it's a simple request, assign to the most suitable agent.
3. Output a JSON list of steps. Each step must have:
   - "agent": Name of the agent (must match one of the available agents).
   - "task": Specific instruction for that agent.
   - "context_needed": List of previous agents' outputs needed (optional).

Example Output:
[
    {{"agent": "Researcher", "task": "Find market trends for smartwatches"}},
    {{"agent": "MarketingTeacher", "task": "Create a marketing plan based on research", "context_needed": ["Researcher"]}}
]

Return ONLY the JSON list. No markdown formatting.
"""

    # 3. Call LLM using correct interface
    from src.core.llm_provider import get_llm_provider
    llm_provider = get_llm_provider()
    
    # Use template + context pattern (compatible with MockLLMProvider)
    result = llm_provider.invoke(system_prompt, {"user_request": user_request})
    
    # Result is already parsed by MockLLMProvider, or we need to extract content
    if isinstance(result, list):
        # MockLLMProvider returns list directly
        plan = result
    elif isinstance(result, dict):
        plan = [result] if result else []
    else:
        # Try to parse as JSON string (for real LLM)
        try:
            content = str(result)
            if hasattr(result, 'content'):
                content = result.content.strip()

            # Use json_repair to handle markdown blocks and fix JSON errors automatically
            import json_repair
            plan = json_repair.loads(content)
        except Exception as e:
            print(f"--- [Supervisor] JSON Parsing Failed: {e} ---")
            plan = None
    
    if plan:
        print(f"--- [Supervisor] Generated Plan: {json.dumps(plan, indent=2, ensure_ascii=False)} ---")
        return {"execution_plan": plan, "next_node": "supervisor_router"}
    else:
        print(f"--- [Supervisor] Failed to parse plan. Fallback to simple routing. ---")
        best_match = registry.find_capable_teacher(user_request, {})
        if best_match:
            return {"execution_plan": [{"agent": best_match, "task": user_request}], "next_node": "supervisor_router"}
        else:
            return {"error": "Could not generate plan and no single agent matched."}

def supervisor_init(state: NexusState) -> Dict[str, Any]:
    """
    Entry point: Inject PRD Context.
    """
    print("--- [Supervisor] Initializing Context ---")
    from src.core.prd_mgr import PRDManager
    
    # 1. Inject PRD Context
    system_constraints = PRDManager.get_system_constraints()
    user_context = state.get("user_context", {})
    prd_file = user_context.get("prd_file", "marketing_prd")
    marketing_constraints = PRDManager.load(prd_file)
    
    prd_context = {
        "system": system_constraints,
        "marketing": marketing_constraints
    }
    
    return {
        "prd_context": prd_context,
        "retry_count": 0,
        "correction_action": None
    }

def router_node(state: NexusState) -> Dict[str, Any]:
    """
    Supervisor 2.0 Router.
    Consumes the Execution Plan and dispatches to agents.
    """
    print("--- [Supervisor] Router ---")
    plan = state.get("execution_plan", [])
    
    if not plan:
        print("--- [Supervisor] Plan Completed ---")
        return {"next_node": "__end__"} # Signal END
        
    # Pop next task
    current_step = plan[0]
    remaining_plan = plan[1:]
    
    agent_name = current_step["agent"]
    task_desc = current_step["task"]
    
    print(f"--- [Supervisor] Dispatching to {agent_name}: {task_desc} ---")
    
    # Map agent name to node name
    # Heuristic: append "_teacher" if not present, or use registry map
    # For now, hardcode mapping based on known agents
    node_mapping = {
        "MarketingTeacher": "marketing_teacher",
        "SupportTeacher": "support_teacher",
        "Researcher": "researcher_teacher"
    }
    
    next_node = node_mapping.get(agent_name, "refusal_node")
    
    # Inject task into messages?
    # Agents usually look at the last message.
    # We should append a system/human message with the specific task.
    # But we don't want to pollute the conversation history visible to user too much?
    # Actually, for internal steps, it's fine.
    
    # Inject task into messages
    # Use dict format to match NexusState definition
    new_message = {"role": "user", "content": f"[Internal Task] {task_desc}"}
    
    return {
        "next_node": next_node,
        "execution_plan": remaining_plan,
        "messages": [new_message],
        "last_teacher": next_node
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
