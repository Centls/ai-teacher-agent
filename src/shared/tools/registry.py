from typing import Callable, Dict, List, Optional

class ToolRegistry:
    _tools: Dict[str, Callable] = {}
    _permissions: Dict[str, List[str]] = {} # tool_name -> [allowed_roles]

    @classmethod
    def register(cls, name: str, func: Callable, allowed_roles: List[str] = ["*"]):
        cls._tools[name] = func
        cls._permissions[name] = allowed_roles

    @classmethod
    def get_tool(cls, name: str, requester_role: str) -> Optional[Callable]:
        if name not in cls._tools:
            raise ValueError(f"Tool {name} not found")
        
        allowed = cls._permissions.get(name, [])
        if "*" in allowed or requester_role in allowed:
            return cls._tools[name]
        
        raise PermissionError(f"Role {requester_role} not authorized for tool {name}")

    @classmethod
    def list_tools(cls) -> List[str]:
        return list(cls._tools.keys())
