from typing import TypedDict, List, Literal

class ToolSchema(TypedDict):
    """
    Structured declaration of a Tool's capabilities and permissions.
    """
    name: str
    description: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    allowed_teachers: List[str]
    required_permissions: List[str]
    supports_dry_run: bool
