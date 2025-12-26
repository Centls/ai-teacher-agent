from ..registry import ToolRegistry

def web_search(query: str) -> str:
    """
    Mock web search.
    """
    return f"Search results for: {query} (Mock Data)"

# Register
ToolRegistry.register("web_search", web_search, allowed_roles=["marketing_teacher", "training_teacher"])
