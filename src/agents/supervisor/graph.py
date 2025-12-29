"""
Supervisor 2.0 - Multi-Agent Orchestration
White-box reuse of agent-service-toolkit's Supervisor pattern.
"""

from typing import Any, List
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

# Import existing agents
from src.agents.marketing.graph import create_marketing_graph

# Configure LLM (DeepSeek)
from src.agents.marketing.llm import llm as deepseek_llm

def get_marketing_agent():
    """
    Wraps the Marketing Graph as an agent for the supervisor.
    """
    graph = create_marketing_graph(with_hitl=False) # Supervisor manages HITL at top level usually, or we let sub-agent handle it?
    # For now, disable HITL in sub-agent to avoid complex nested interrupts
    graph.name = "MarketingTeacher"
    return graph

def create_general_agent():
    """
    A simple general chat agent.
    """
    # We can use a simple runnable or a graph
    async def general_chat_node(state):
        messages = state["messages"]
        response = await deepseek_llm.ainvoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(dict)
    workflow.add_node("general_chat", general_chat_node)
    workflow.set_entry_point("general_chat")
    workflow.add_edge("general_chat", END)
    graph = workflow.compile()
    graph.name = "GeneralAssistant"
    return graph

def create_nexus_supervisor(checkpointer=None):
    """
    Creates the Supervisor 2.0 graph managing multiple teachers.
    """
    marketing_agent = get_marketing_agent()
    general_agent = create_general_agent()
    
    agents = [marketing_agent, general_agent]
    
    # Create supervisor workflow
    # Note: create_supervisor returns a CompiledGraph
    workflow = create_supervisor(
        agents,
        model=deepseek_llm,
        prompt=(
            "You are the Nexus Supervisor, managing a team of AI Teachers. "
            "For marketing questions, consult the MarketingTeacher. "
            "For general questions or greetings, use the GeneralAssistant. "
            "Always route to the most appropriate expert."
        ),
        add_handoff_back_messages=True,
        output_mode="full_history",
    )
    
    return workflow.compile(checkpointer=checkpointer)
