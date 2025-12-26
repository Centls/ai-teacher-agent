from langgraph.graph import StateGraph, END
from src.core.factory import GraphFactory
from .state import MarketingState
from .nodes import plan_node, execute_node, review_node
from ..base import BaseTeacher

class MarketingTeacher(BaseTeacher):
    def compile_graph(self):
        workflow = StateGraph(MarketingState)
        
        # Add Nodes
        workflow.add_node("plan", GraphFactory.create_node_wrapper("marketing_plan", plan_node))
        workflow.add_node("execute", GraphFactory.create_node_wrapper("marketing_execute", execute_node))
        workflow.add_node("review", GraphFactory.create_node_wrapper("marketing_review", review_node))
        
        # Define Edges
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "review")
        workflow.add_edge("review", END)
        
        return GraphFactory.compile(workflow)

    def capability(self):
        from src.core.capability import CapabilitySchema
        return CapabilitySchema(
            name="marketing",
            description="Expert in creating marketing strategies, content plans, and copywriting.",
            supported_tasks=["marketing_plan", "copywriting", "brand_strategy", "market_analysis", "promotion", "promote", "营销计划", "文案", "品牌", "市场分析", "推广"],
            required_inputs=["prd_constraints", "user_request"],
            forbidden_outputs=["financial_advice", "legal_advice"],
            supports_multimodal=False,
            degradation_modes=["mock_response"]
        )
