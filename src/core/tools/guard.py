import time
from typing import Any, Dict, Optional, Callable
from src.core.audit import audit_logger
from .schema import ToolSchema

class ToolInvocationGuard:
    def __init__(self, tool_schema: ToolSchema):
        self.schema = tool_schema

    def invoke(self, teacher_name: str, tool_func: Callable, kwargs: Dict[str, Any], dry_run: bool = False) -> Any:
        # Permission Check
        if teacher_name not in self.schema["allowed_teachers"]:
            error_msg = f"Teacher '{teacher_name}' is not allowed to use tool '{self.schema['name']}'"
            audit_logger.log_event("tool_invocation_denied", "global", {
                "teacher": teacher_name,
                "tool": self.schema["name"],
                "reason": "PERMISSION_DENIED"
            })
            raise PermissionError(error_msg)

        # Audit Start
        start_time = time.time()
        status = "SUCCESS"
        error = None
        result = None

        try:
            if dry_run and self.schema["supports_dry_run"]:
                print(f"[Guard] Dry Run: {self.schema['name']} with {kwargs}")
                result = {"status": "DRY_RUN", "message": "Tool executed in dry run mode"}
            else:
                result = tool_func(**kwargs)
        except Exception as e:
            status = "ERROR"
            error = str(e)
            raise e
        finally:
            duration = (time.time() - start_time) * 1000
            audit_logger.log_event("tool_invocation", "global", {
                "teacher": teacher_name,
                "tool": self.schema["name"],
                "args": str(kwargs),
                "status": status,
                "error": error,
                "duration_ms": duration,
                "dry_run": dry_run
            })
        
        return result
