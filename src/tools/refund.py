from src.core.tools.schema import ToolSchema

def refund_func(user_id: str, amount: float, reason: str):
    # Mock implementation
    return {"status": "SUCCESS", "transaction_id": "txn_mock_123", "message": f"Refunded ${amount} to {user_id}"}

REFUND_TOOL_SCHEMA: ToolSchema = {
    "name": "refund_tool",
    "description": "Process a refund for a user.",
    "risk_level": "HIGH",
    "allowed_teachers": ["support"],
    "required_permissions": ["finance_access"],
    "supports_dry_run": True
}
