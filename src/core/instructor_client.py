# -*- coding: utf-8 -*-
"""
Instructor Client 统一入口

强依赖复用：
- instructor: 结构化输出库（完整复用，不重写）
- langsmith: 追踪装饰器（完整复用，不重写）
- openai: OpenAI 兼容 API（完整复用）

职责边界：
- 本模块仅负责 Client 初始化与追踪装饰
- 结构化输出逻辑由 instructor 库完整实现
- 追踪逻辑由 langsmith 库完整实现

使用方式：
    from src.core.instructor_client import get_instructor_client, traced

    client = get_instructor_client()

    @traced(name="my_function")
    def my_function():
        return client.chat.completions.create(
            model=settings.DEFAULT_MODEL,
            response_model=MySchema,
            messages=[...]
        )
"""

import logging
from functools import wraps
from typing import Optional, Callable, Any, TypeVar

# ========== 强依赖：完整复用，不重写 ==========
import instructor
from openai import OpenAI

from config.settings import settings

logger = logging.getLogger(__name__)

# 类型变量
T = TypeVar('T')

# 单例缓存
_client: Optional[instructor.Instructor] = None


def get_instructor_client() -> instructor.Instructor:
    """
    获取 Instructor Client 单例

    强依赖：instructor.from_openai（完整复用）

    复用项目现有的 API 配置（DeepSeek/阿里云），不增加额外费用。

    Returns:
        instructor.Instructor: Instructor 包装的 OpenAI Client
    """
    global _client

    if _client is None:
        # 依赖：instructor.from_openai（完整复用，不重写）
        _client = instructor.from_openai(
            OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE
            ),
            mode=instructor.Mode.MD_JSON  # MD_JSON 模式，兼容性最好
        )
        logger.info("✅ Instructor Client 初始化完成（单例模式）")

    return _client


def traced(name: str, run_type: str = "chain") -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    LangSmith 追踪装饰器

    强依赖：langsmith.traceable（完整复用，不重写）

    让 Instructor 调用也能被 LangSmith 追踪，与 LangChain 调用链统一。

    Args:
        name: 追踪名称（在 LangSmith UI 中显示）
        run_type: 运行类型（chain/llm/tool/retriever）

    Returns:
        装饰器函数

    使用方式：
        @traced(name="query_understanding")
        def analyze_query(query: str) -> QueryAnalysis:
            client = get_instructor_client()
            return client.chat.completions.create(...)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                # 依赖：langsmith.traceable（完整复用，不重写）
                from langsmith import traceable
                traced_func = traceable(name=name, run_type=run_type)(func)
                return traced_func(*args, **kwargs)
            except ImportError:
                # LangSmith 未安装，直接执行（降级）
                logger.debug(f"LangSmith not available, running '{name}' without tracing")
                return func(*args, **kwargs)
            except Exception as e:
                # 追踪失败，降级执行（保证功能可用）
                logger.warning(f"LangSmith tracing failed for '{name}': {e}, running without tracing")
                return func(*args, **kwargs)

        return wrapper
    return decorator


def get_model_name() -> str:
    """获取当前配置的模型名称"""
    return getattr(settings, 'DEFAULT_MODEL', 'deepseek-chat')