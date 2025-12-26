from src.core.tools.schema import ToolSchema

def publish_func(platform: str, content: str):
    # Mock implementation
    return {"status": "SUCCESS", "post_id": "post_mock_456", "url": f"https://{platform}.com/post/mock"}

PUBLISH_TOOL_SCHEMA: ToolSchema = {
    "name": "publish_tool",
    "description": "Publish content to social media platforms.",
    "risk_level": "MEDIUM",
    "allowed_teachers": ["marketing"],
    "required_permissions": ["social_media_write"],
    "supports_dry_run": True
}
