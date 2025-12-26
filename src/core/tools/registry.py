from typing import Dict, Any, Callable
from .schema import ToolSchema
from .guard import ToolInvocationGuard

class ToolRegistry:
    _instance = None
    
    def __init__(self):
        self._tools: Dict[str, ToolSchema] = {}
        self._funcs: Dict[str, Callable] = {}
        self._guards: Dict[str, ToolInvocationGuard] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ToolRegistry()
        return cls._instance

    def register(self, schema: ToolSchema, func: Callable):
        name = schema["name"]
        self._tools[name] = schema
        self._funcs[name] = func
        self._guards[name] = ToolInvocationGuard(schema)
        print(f"[ToolRegistry] Registered tool: {name}")

    def request_execution(self, teacher_name: str, tool_name: str, kwargs: Dict[str, Any], dry_run: bool = False) -> Any:
        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        guard = self._guards[tool_name]
        func = self._funcs[tool_name]
        
        return guard.invoke(teacher_name, func, kwargs, dry_run)
