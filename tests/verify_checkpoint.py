import sys
import os
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.lifecycle import SessionManager
from src.supervisor.graph import create_supervisor_graph

def verify_memory_resume():
    print("=== Verifying Memory & Checkpoint (In-Memory) ===")
    
    # 1. Initialize
    user_id = "test_user"
    session_id = SessionManager.create_session(user_id)
    print(f"Session Created: {session_id}")
    
    # 2. Build Graph
    app = create_supervisor_graph()
    
    # 3. First Run (Initial Request)
    print("\n--- Run 1: Initial Request ---")
    initial_state = SessionManager.get_session(session_id)
    initial_state["messages"] = [{"role": "user", "content": "I need a marketing plan."}]
    initial_state["user_context"] = {"user_id": user_id, "prd_file": "marketing_prd"}
    
    thread_id = SessionManager.get_thread_id(session_id)
    config = {"configurable": {"thread_id": thread_id}}
    
    # We use stream to see steps, or just invoke
    result1 = app.invoke(initial_state, config=config)
    print("Run 1 Completed.")
    print(f"Messages count: {len(result1['messages'])}")
    
    # 4. Simulate Resume (Second Run with same thread_id)
    print("\n--- Run 2: Resume (Follow-up) ---")
    # In a real resume, we might pass new input, or just continue.
    # Let's pass a follow-up question. 
    # LangGraph with Checkpointer should load the PREVIOUS state and append this new message.
    
    # Note: We do NOT pass the full state again, just the new message (if LangGraph supports it)
    # OR we pass the state update.
    # For StateGraph, we usually pass the input update.
    
    new_input = {"messages": [{"role": "user", "content": "Make it shorter."}]}
    
    result2 = app.invoke(new_input, config=config)
    print("Run 2 Completed.")
    print(f"Messages count: {len(result2['messages'])}")
    
    # 5. Verification
    # If memory works, result2['messages'] should contain messages from Run 1 AND Run 2.
    # Run 1: User + AI (approx 2-4 messages depending on graph depth)
    # Run 2: User + AI (approx 2 more)
    
    if len(result2["messages"]) > len(new_input["messages"]):
        print("\n✅ VERIFICATION PASSED: State was preserved across invokes.")
        print(f"Total History: {[m['role'] for m in result2['messages']]}")
    else:
        print("\n❌ VERIFICATION FAILED: State was lost.")

if __name__ == "__main__":
    verify_memory_resume()
