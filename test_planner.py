import sys
sys.path.insert(0, '.')
from src.agents.supervisor.nodes import planner_node

# Minimal state
state = {
    "messages": [{"role": "user", "content": "Research TCM Watch and create marketing plan"}],
    "user_context": {}
}

try:
    result = planner_node(state)
    print("SUCCESS:", result)
except Exception as e:
    print("ERROR:", e)
    import traceback
    traceback.print_exc()
