"""
AI 营销老师 - LangGraph 工作流定义

复用来源: 
- Agentic-RAG-Ollama (CRAG 工作流)
- agent-service-toolkit (HITL interrupt_before)
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

# Import Local Nodes (White-box Reuse)
from .nodes import (
    MarketingState,
    retrieve_node,
    grade_documents_node,
    generate_node,
    transform_query_node,
    check_answer_quality,
    should_generate,
    check_hallucination_router,
    human_approval_node,
    check_approval,
    learning_node
)

def create_marketing_graph(checkpointer: BaseCheckpointSaver = None, store: BaseStore = None, with_hitl: bool = True):
    """
    创建营销老师 LangGraph 工作流 (White-box Reuse of Agentic-RAG CRAG)
    """
    
    # 创建状态图
    workflow = StateGraph(MarketingState)
    
    # ==========================================================================
    # 添加节点
    # ==========================================================================
    
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade_documents", grade_documents_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("transform_query", transform_query_node)
    workflow.add_node("check_answer_quality", check_answer_quality)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("learning", learning_node)
    
    # ==========================================================================
    # 定义边
    # ==========================================================================
    
    workflow.set_entry_point("retrieve")
    
    workflow.add_edge("retrieve", "grade_documents")
    
    workflow.add_conditional_edges(
        "grade_documents",
        should_generate,
        {
            "generate": "human_approval" if with_hitl else "generate",  # 根据 with_hitl 决定是否审批
            "transform_query": "transform_query"
        }
    )

    workflow.add_conditional_edges(
        "human_approval",
        check_approval,
        {
            "generate": "generate",
            "transform_query": "transform_query"
        }
    )
    
    workflow.add_edge("transform_query", "retrieve")
    workflow.add_edge("generate", "check_answer_quality")
    
    workflow.add_conditional_edges(
        "check_answer_quality",
        check_hallucination_router,
        {
            "useful": "learning",
            "not useful": "transform_query",
            "not supported": "transform_query"
        }
    )
    
    workflow.add_edge("learning", END)
    
    # ==========================================================================
    # 编译图
    # ==========================================================================
    
    if with_hitl:
        graph = workflow.compile(
            checkpointer=checkpointer,
            store=store
            # interrupt_before removed, using interrupt() in human_approval_node
        )
    else:
        graph = workflow.compile(checkpointer=checkpointer, store=store)
    
    return graph
