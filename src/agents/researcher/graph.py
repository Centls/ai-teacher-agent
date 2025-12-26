from langgraph.graph import StateGraph, END
from src.core.factory import GraphFactory
from src.agents.teachers.base import BaseTeacher
from .state import ResearcherState
from .nodes import research_node

class Researcher(BaseTeacher):
    def compile_graph(self):
        workflow = StateGraph(ResearcherState)
        
        # Add Nodes
        # research_node is async, GraphFactory handles it
        workflow.add_node("research", GraphFactory.create_node_wrapper("research_execute", research_node))
        
        # Define Edges
        workflow.set_entry_point("research")
        workflow.add_edge("research", END)
        
        return GraphFactory.compile(workflow)

    def capability(self):
        from src.core.capability import CapabilitySchema
        return CapabilitySchema(
            name="researcher",
            description="Expert in researching topics using GPT Researcher (Deep Research).",
            supported_tasks=["research", "search", "find_info", "summarize", "news", "latest_events", "搜索", "查找", "研究", "总结", "新闻", "原理", "介绍"],
            required_inputs=["user_request"],
            forbidden_outputs=[],
            supports_multimodal=False,
            degradation_modes=["mock_response"]
        )
