from typing import Dict
from .provider import KnowledgeProvider

class MockKnowledgeProvider(KnowledgeProvider):
    """
    Mock implementation of Knowledge Provider for testing.
    """
    
    def __init__(self):
        # Mock Data Store
        self.data: Dict[str, str] = {
            "TCM手表": "TCM手表是一种结合中医理念的智能穿戴设备，能够通过脉搏监测提供健康建议，如根据节气推荐饮食。",
            "ZenPulse": "ZenPulse 是心宇未来推出的旗舰款TCM手表，主打年轻人的'朋克养生'市场。",
            "AI Agent": "AI Agent 是具备感知、规划、行动能力的智能体系统，2024年的趋势是多智能体协作(Multi-Agent)。"
        }

    def query(self, query_text: str) -> str:
        """
        Simple keyword matching for mock data.
        """
        print(f"--- [MockRAG] Querying: {query_text} ---")
        
        # Exact match
        if query_text in self.data:
            return self.data[query_text]
            
        # Partial match
        for key, value in self.data.items():
            if key in query_text:
                return value
                
        return "暂无相关资料"
