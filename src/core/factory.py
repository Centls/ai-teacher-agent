from typing import Callable, Any, Dict
from langchain_core.runnables import RunnableConfig
import time
from langgraph.graph import StateGraph, END
from .audit import audit_logger
from .state_mgr import NexusState

class GraphFactory:
    """
    Factory to compile graphs with standard injections (Audit, Error Handling).
    """
    
    @staticmethod
    def create_node_wrapper(node_name: str, node_func: Callable) -> Callable:
        """
        Wraps a node function with audit logging and error handling.
        Supports both sync and async nodes.
        """
        import inspect
        import asyncio

        if inspect.iscoroutinefunction(node_func):
            async def wrapped_node(state: NexusState, config: RunnableConfig = None) -> Dict:
                start_time = time.time()
                session_id = state.get("meta", {}).get("session_id", "unknown")
                
                try:
                    # Execute Async Node
                    result = await node_func(state)
                    
                    # Log Success
                    duration = time.time() - start_time
                    audit_logger.log_node_execution(session_id, node_name, state, result, duration)
                    
                    return result
                except Exception as e:
                    # Log Error
                    duration = time.time() - start_time
                    audit_logger.log_event("node_error", session_id, {"node": node_name, "error": str(e)})
                    
                    # Return Error State
                    return {"error": str(e), "status": "FALLBACK"}
            return wrapped_node
        else:
            def wrapped_node(state: NexusState, config: RunnableConfig = None) -> Dict:
                start_time = time.time()
                session_id = state.get("meta", {}).get("session_id", "unknown")
                
                try:
                    # Execute Sync Node
                    result = node_func(state)
                    
                    # Log Success
                    duration = time.time() - start_time
                    audit_logger.log_node_execution(session_id, node_name, state, result, duration)
                    
                    return result
                except Exception as e:
                    # Log Error
                    duration = time.time() - start_time
                    audit_logger.log_event("node_error", session_id, {"node": node_name, "error": str(e)})
                    
                    # Return Error State
                    return {"error": str(e), "status": "FALLBACK"}
            return wrapped_node

    @classmethod
    def compile(cls, workflow: StateGraph, checkpointer=None):
        """
        Compiles the graph with optional checkpointer.
        Auto-injects JSONLCheckpointSaver if not provided.
        """
        if checkpointer is None:
            # from src.core.checkpoint.jsonl import JSONLCheckpointSaver
            # checkpointer = JSONLCheckpointSaver()
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
            
        return workflow.compile(checkpointer=checkpointer)
