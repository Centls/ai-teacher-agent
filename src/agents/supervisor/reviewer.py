from src.core.state_mgr import NexusState
from typing import Dict, Any

def reviewer_node(state: NexusState) -> Dict[str, Any]:
    print("--- Supervisor: Reviewing Output (Self-Reflection) ---")
    
    # 1. Get Context
    messages = state.get("messages", [])
    if not messages:
        return {"correction_action": "ACCEPT"}
        
    last_message = messages[-1]
    content = last_message["content"]
    
    retry_count = state.get("retry_count", 0) or 0
    MAX_RETRIES = 1
    
    # 2. Check Retry Limit
    if retry_count >= MAX_RETRIES:
        print(f"--- Reviewer: Max retries ({MAX_RETRIES}) reached. Forcing ACCEPT. ---")
        return {
            "correction_action": "ACCEPT",
            "reflection_issues": ["Max retries reached"],
            "reflection_score": 0.5
        }

    # 3. Evaluation Logic (Mock/Heuristic)
    # In a real system, this would be an LLM call comparing 'content' vs 'prd_context'
    # For DEMO purposes: We look for a specific trigger keyword "RETRY_ME" in the content
    # OR if the content is too short (< 10 chars)
    
    issues = []
    score = 1.0
    action = "ACCEPT"
    
    # Demo Logic: If content contains "make it shorter" (from our verification script), we accept.
    # But if we want to demonstrate RETRY, we need a trigger.
    # Let's say if the content contains "Draft", we ask for "Final".
    # Or simpler: We inject a "force_retry" flag in user_context for the demo.
    
    user_context = state.get("user_context", {})
    force_retry = user_context.get("force_retry_once", False)
    
    if force_retry and retry_count == 0:
        issues.append("Output marked for forced retry demonstration.")
        score = 0.4
        action = "RETRY"
        print("--- Reviewer: Detected forced retry trigger. Requesting Correction. ---")
        
        # Add a feedback message to guide the Teacher
        feedback_msg = {"role": "user", "content": "The reviewer found issues: Output marked for forced retry. Please refine."}
        return {
            "reflection_score": score,
            "reflection_issues": issues,
            "correction_action": action,
            "retry_count": retry_count + 1,
            "messages": [feedback_msg]
        }
        
    # 4. Real Logic (Stub)
    # if len(content) < 50:
    #     issues.append("Content too short")
    #     action = "RETRY"
    
    print(f"--- Reviewer: Decision = {action} (Score: {score}) ---")
    
    return {
        "reflection_score": score,
        "reflection_issues": issues,
        "correction_action": action,
        "retry_count": retry_count # Keep same if accept
    }
