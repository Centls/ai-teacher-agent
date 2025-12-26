import sys
import os
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.lifecycle import SessionManager
from src.core.config_mgr import ConfigManager
from src.supervisor.graph import create_supervisor_graph
from src.core.state_mgr import NexusState

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== AI Teacher Nexus CLI Demo ===")
    
    # 1. Initialize
    user_id = "user_123"
    session_id = SessionManager.create_session(user_id)
    
    # 2. Load Config
    ConfigManager.reload_config()
    
    # 3. Build Graph
    app = create_supervisor_graph()
    
    # 4. Simulate User Request
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="I need a marketing plan for my new coffee shop.")
    parser.add_argument("--prd", default="marketing_prd", help="PRD file name (without extension)")
    parser.add_argument("--resume", help="Session ID to resume from", default=None)
    parser.add_argument("--demo-reflection", action="store_true", help="Trigger self-reflection demo (force retry)")
    parser.add_argument("--web-sim", action="store_true", help="Simulate Web API Call (Structured Input/Output)")
    args = parser.parse_args()
    
    user_input = args.query
    prd_file = args.prd
    resume_session_id = args.resume
    
    if resume_session_id:
        print(f"Resuming session: {resume_session_id}")
        session_id = resume_session_id
        # Note: In a real resume scenario, we might not want to overwrite initial_state messages
        # if we are just continuing. But for now, let's assume we might provide new input or just continue.
        # If resuming, we should probably load the state from checkpoint, but LangGraph does that automatically
        # if we pass the same thread_id.
    
    print(f"\nUser Input: {user_input}")
    print(f"Using PRD: {prd_file}\n")
    
    initial_state = SessionManager.get_session(session_id)
    if not initial_state:
         # If resuming from a cold start (CLI restart), recreate the session structure
         # The actual state will be loaded from checkpoint by LangGraph
         SessionManager.create_session(user_id) # This creates a new ID, we need to force the old one if resuming
         if resume_session_id:
             # Manually inject the old session ID if we are simulating a resume
             # In a real app, SessionManager would load from DB.
             # Here we just rely on LangGraph Checkpointer to restore the graph state.
             pass

    if initial_state:
        initial_state["messages"] = [{"role": "user", "content": user_input}]
        initial_state["user_context"] = {
            "user_id": "user_123", 
            "prd_file": prd_file,
            "force_retry_once": args.demo_reflection
        }
    else:
        # If we are resuming and SessionManager doesn't have it (fresh process), 
        # we pass a minimal state or None, relying on LangGraph to load from checkpoint.
        # However, LangGraph invoke needs an input.
        # If we pass input, it updates the state.
        initial_state = {
            "messages": [{"role": "user", "content": user_input}],
            "user_context": {
                "user_id": "user_123", 
                "prd_file": prd_file,
                "force_retry_once": args.demo_reflection
            }
        }
    
    # 5. Run Graph
    print("--- Execution Start ---")
    try:
        thread_id = SessionManager.get_thread_id(session_id)
        config = {"configurable": {"thread_id": thread_id}}
        
        final_state = app.invoke(initial_state, config=config)
        
        print("\n--- Execution End ---")
        print("\n--- Execution End ---")
        
        # Enhanced Status Output
        exec_result = final_state.get("execution_result")
        
        if args.web_sim:
            print("\n=== WEB API RESPONSE (Simulated) ===")
            import json
            # Serialize Envelope to JSON
            print(json.dumps(exec_result, indent=2, default=str))
            print("====================================")
        else:
            # Show Routing Decision (Inferred from final state or logs)
            # Since we don't store routing decision in state explicitly, we can infer it from the last active node if we tracked it.
            # But for now, let's just show the final status.
            # Ideally, we should add "routing_decision" to NexusState.
            
            if exec_result:
                status = exec_result.get("status", "UNKNOWN")
                reason = exec_result.get("reason_code", "NONE")
                message = exec_result.get("message", "")
                print(f"Final Status: {status}")
                print(f"Reason Code: {reason}")
                if message:
                    print(f"Message: {message}")
                if exec_result.get("diagnostics"):
                    print(f"Diagnostics: {exec_result['diagnostics']}")
            else:
                # Check for Refusal (No Capable Teacher)
                # If we ended without execution_result, it might be a refusal from router.
                print("Final Status:", final_state.get("status", "REFUSED (No Capable Agent)"))
                
            print("Last Message:", final_state["messages"][-1]["content"] if final_state["messages"] else "No response")
        
    except Exception as e:
        print(f"Execution Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Cleanup
    SessionManager.close_session(session_id)

if __name__ == "__main__":
    main()
