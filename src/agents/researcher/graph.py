from langgraph.graph import StateGraph, END
from src.core.factory import GraphFactory
from src.agents.teachers.base import BaseTeacher
from .state import ResearcherState
from .nodes import plan_research_node, execute_search_node, summarize_node

class Researcher(BaseTeacher):
    def compile_graph(self):
        workflow = StateGraph(ResearcherState)
        
        # Add Nodes
        workflow.add_node("plan", GraphFactory.create_node_wrapper("research_plan", plan_research_node))
        workflow.add_node("search", GraphFactory.create_node_wrapper("research_search", execute_search_node))
        workflow.add_node("summarize", GraphFactory.create_node_wrapper("research_summarize", summarize_node))
        
        # Define Edges
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "search")
        workflow.add_edge("search", "summarize")
        workflow.add_edge("summarize", END)
        
        return GraphFactory.compile(workflow)

    def capability(self):
        from src.core.capability import CapabilitySchema
        return CapabilitySchema(
            name="researcher",
            description="Expert in researching topics, gathering information from the web, and summarizing findings.",
            supported_tasks=["research", "search", "find_info", "summarize", "news", "latest_events", "搜索", "查找", "研究", "总结", "新闻", "原理", "介绍"],
            required_inputs=["user_request"],
            forbidden_outputs=[],
            supports_multimodal=False,
            degradation_modes=["mock_response"]
        )
