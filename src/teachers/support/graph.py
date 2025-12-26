from langgraph.graph import StateGraph, END
from src.core.factory import GraphFactory
from .state import SupportState
from .nodes import boundary_check_node, answer_node, confidence_review_node
from ..base import BaseTeacher

class SupportTeacher(BaseTeacher):
    def compile_graph(self):
        workflow = StateGraph(SupportState)
        
        # Add Nodes
        workflow.add_node("boundary_check", GraphFactory.create_node_wrapper("support_boundary", boundary_check_node))
        workflow.add_node("answer", GraphFactory.create_node_wrapper("support_answer", answer_node))
        workflow.add_node("review", GraphFactory.create_node_wrapper("support_review", confidence_review_node))
        
        # Define Edges
        workflow.set_entry_point("boundary_check")
        
        def check_boundary(state):
            if state.get("boundary_check_result") == "FAIL":
                return END
            return "answer"
            
        workflow.add_conditional_edges(
            "boundary_check",
            check_boundary,
            {
                END: END,
                "answer": "answer"
            }
        )
        
        workflow.add_edge("answer", "review")
        workflow.add_edge("review", END)
        
        return GraphFactory.compile(workflow)

    def capability(self):
        from src.core.capability import CapabilitySchema
        return CapabilitySchema(
            name="support",
            description="Handles customer support queries, FAQs, and refund policies.",
            supported_tasks=["customer_support", "faq", "refund_policy", "refund", "troubleshooting"],
            required_inputs=["user_request"],
            forbidden_outputs=["medical_advice", "political_opinion"],
            supports_multimodal=False,
            degradation_modes=["mock_response"]
        )
