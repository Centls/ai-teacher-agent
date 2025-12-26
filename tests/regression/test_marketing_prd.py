import sys
import os
from pathlib import Path
# import pytest

# Add src to python path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.lifecycle import SessionManager
from src.core.config_mgr import ConfigManager
from src.supervisor.graph import create_supervisor_graph

def test_marketing_prd_compliance():
    """
    Regression Test: Verify Marketing Teacher output complies with PRD.
    Runs in Mock mode (implied by environment or lack of key).
    """
    # 1. Setup
    user_id = "test_user"
    session_id = SessionManager.create_session(user_id)
    ConfigManager.reload_config()
    app = create_supervisor_graph()
    
    # 2. Input
    user_input = "I need a marketing plan for my new coffee shop."
    initial_state = SessionManager.get_session(session_id)
    initial_state["messages"] = [{"role": "user", "content": user_input}]
    
    # 3. Execution
    final_state = app.invoke(initial_state)
    
    # 4. Assertions
    # Status
    assert final_state.get("status") == "SUCCESS", "Execution should be successful"
    
    # Output Content
    last_message = final_state["messages"][-1]["content"]
    assert "Marketing Plan (PRD Compliant)" in last_message
    assert "Core Positioning" in last_message
    assert "Channel Strategy" in last_message
    
    # PRD Compliance Flag (from Review Node)
    assert final_state.get("prd_compliance") == "PASS", "PRD Compliance should be PASS"
    
    # Mock Specifics (Proof that MockLLMProvider is working and aligned)
    assert "(Mock)" in last_message, "Output should contain Mock indicators"
    
    print("Regression Test Passed: Marketing PRD Compliance")

if __name__ == "__main__":
    test_marketing_prd_compliance()
