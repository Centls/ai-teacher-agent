from typing import TypedDict, Optional
from src.core.state_mgr import NexusState

class MarketingState(NexusState):
    """
    Marketing specific state extensions.
    """
    marketing_plan: Optional[str]
    target_audience: Optional[str]
    product_description: Optional[str]
    channel_strategy: Optional[dict] # {channel: strategy}
    content_plan: Optional[list] # List of content items
    execution_steps: Optional[list] # List of steps
    quality_score: Optional[int] # 0-100
