from ..registry import ToolRegistry

def db_query(sql: str) -> str:
    return "DB Result (Mock)"

# High privilege tool
ToolRegistry.register("db_query", db_query, allowed_roles=["admin"])
