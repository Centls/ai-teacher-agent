import sys
import os
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.tools.registry import ToolRegistry
from src.tools.publish import PUBLISH_TOOL_SCHEMA, publish_func

# Register
registry = ToolRegistry.get_instance()
# Note: In a real run, registry is a singleton and might already have tools if imported from main, 
# but here we are in a standalone script.
registry.register(PUBLISH_TOOL_SCHEMA, publish_func)

print("--- Testing Unauthorized Access ---")
try:
    registry.request_execution(
        teacher_name="support", # Not in allowed_teachers for publish_tool
        tool_name="publish_tool",
        kwargs={"platform": "X", "content": "test"}
    )
    print("FAILED: Should have raised PermissionError")
except PermissionError as e:
    print(f"SUCCESS: Caught expected error: {e}")
except Exception as e:
    print(f"FAILED: Caught unexpected error: {type(e)}: {e}")
