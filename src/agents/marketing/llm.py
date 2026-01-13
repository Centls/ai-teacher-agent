"""
AI 营销老师 - LLM 配置模块

复用来源: Agentic-RAG-Ollama (替换 ChatOllama 为 ChatOpenAI/DeepSeek)
"""

from config.settings import settings
from langchain_openai import ChatOpenAI


def get_llm(temperature: float = 0.7, streaming: bool = True) -> ChatOpenAI:
    """
    获取 DeepSeek LLM 实例
    
    Args:
        temperature: 生成温度 (0.0-1.0)
        streaming: 是否启用流式输出
    
    Returns:
        ChatOpenAI: 配置好的 DeepSeek LLM 实例
    """
    return ChatOpenAI(
        model=settings.DEFAULT_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_api_base=settings.OPENAI_API_BASE,
        temperature=temperature,
        streaming=streaming,
    )


# 默认 LLM 实例
llm = get_llm()
