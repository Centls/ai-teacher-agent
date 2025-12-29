"""
AI 营销老师 - LLM 配置模块

复用来源: Agentic-RAG-Ollama (替换 ChatOllama 为 ChatOpenAI/DeepSeek)
"""

import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


def get_llm(temperature: float = 0.7, streaming: bool = True) -> ChatOpenAI:
    """
    获取 DeepSeek LLM 实例
    
    Args:
        temperature: 生成温度 (0.0-1.0)
        streaming: 是否启用流式输出
    
    Returns:
        ChatOpenAI: 配置好的 DeepSeek LLM 实例
    """
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    api_base = os.getenv("LLM_API_BASE") or os.getenv("DEEPSEEK_API_BASE") or os.getenv("OPENAI_API_BASE") or "https://api.deepseek.com/v1"
    
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        openai_api_key=api_key,
        openai_api_base=api_base,
        temperature=temperature,
        streaming=streaming,
    )


# 默认 LLM 实例
llm = get_llm()
