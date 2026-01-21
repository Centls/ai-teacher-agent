"""
统一日志配置模块

日志文件结构：
- logs/server.log      # API 请求、启动信息、配置加载
- logs/knowledge.log   # 知识库操作：上传、删除、向量化
- logs/docling.log     # 文档解析：OCR、格式转换、耗时
- logs/rag.log         # RAG 底层：ChromaDB 操作、BM25 检索
- logs/error.log       # 所有错误汇总（跨模块）

策略：
- 按日期轮转，每天一个文件
- 保留 7 天历史
- 单文件最大 50MB
- 每次启动写入分隔标记

依赖：Python 标准库 logging（完整复用）
"""

import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

# 日志目录
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 日志格式
FILE_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CONSOLE_FORMAT = "%(message)s"

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class MaxSizeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    结合时间轮转和大小限制的日志处理器

    - 每天 0 点自动轮转
    - 单文件超过 maxBytes 也会轮转
    - 保留 backupCount 个历史文件

    强依赖：logging.handlers.TimedRotatingFileHandler（完整复用）
    """

    def __init__(self, filename, when='midnight', interval=1,
                 backupCount=7, maxBytes=50*1024*1024, encoding='utf-8'):
        super().__init__(
            filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding
        )
        self.maxBytes = maxBytes

    def shouldRollover(self, record):
        # 先检查时间轮转
        if super().shouldRollover(record):
            return True
        # 再检查大小限制
        if self.maxBytes > 0:
            if self.stream is None:
                self.stream = self._open()
            try:
                self.stream.seek(0, 2)  # 移到文件末尾
                if self.stream.tell() + len(self.format(record)) >= self.maxBytes:
                    return True
            except (OSError, ValueError):
                pass
        return False


class LoggerFactory:
    """
    日志工厂类 - 统一管理所有日志器

    使用方式：
        from src.core.logging_config import LoggerFactory
        logger = LoggerFactory.get_logger("knowledge")
        logger.info("文档上传成功", extra={"file": "test.pdf", "size": "1.2MB"})
    """

    _loggers: dict = {}
    _initialized: bool = False
    _console_handler: Optional[logging.Handler] = None
    _error_handler: Optional[logging.Handler] = None

    # 日志器配置
    LOGGER_CONFIG = {
        "server": {
            "file": "server.log",
            "level": "INFO",
            "description": "API 请求、启动信息、配置加载"
        },
        "knowledge": {
            "file": "knowledge.log",
            "level": "INFO",
            "description": "知识库操作：上传、删除、向量化"
        },
        "docling_client": {
            "file": "docling_client.log",
            "level": "INFO",
            "description": "调用 Docling API 的请求/响应/耗时"
        },
        "rag": {
            "file": "rag.log",
            "level": "INFO",
            "description": "RAG 底层：ChromaDB 操作、BM25 检索"
        },
    }

    @classmethod
    def init(cls, console_level: str = "INFO", file_level: str = "DEBUG"):
        """
        初始化日志系统

        应在应用启动时调用一次：
            LoggerFactory.init()
        """
        if cls._initialized:
            return

        # ========== 捕获第三方库日志（transformers, chromadb 等）==========
        # 这些库的警告默认输出到 stderr，需要重定向到 logging
        import warnings
        logging.captureWarnings(True)  # 将 warnings 模块输出重定向到 logging

        # 创建 server.log 的文件处理器（用于第三方库日志）
        server_file = LOGS_DIR / "server.log"
        server_file_handler = MaxSizeTimedRotatingFileHandler(
            str(server_file),
            when='midnight',
            backupCount=7,
            maxBytes=50*1024*1024,
            encoding='utf-8'
        )
        server_file_handler.setLevel(logging.WARNING)  # 只记录 WARNING 及以上
        server_file_handler.setFormatter(
            logging.Formatter(FILE_FORMAT, datefmt=FILE_DATE_FORMAT)
        )

        # 配置第三方库的日志器，使其输出到 server.log
        third_party_loggers = [
            "transformers",           # HuggingFace transformers
            "sentence_transformers",  # Sentence Transformers
            "chromadb",               # ChromaDB
            "httpx",                  # HTTP 客户端
            "httpcore",               # HTTP 核心
            "py.warnings",            # Python warnings 模块（通过 captureWarnings）
        ]
        for lib_name in third_party_loggers:
            lib_logger = logging.getLogger(lib_name)
            lib_logger.setLevel(logging.WARNING)  # 只记录警告及以上
            lib_logger.addHandler(server_file_handler)

        # 创建共享的控制台处理器（使用 Rich 如果可用）
        try:
            from rich.logging import RichHandler
            cls._console_handler = RichHandler(
                rich_tracebacks=True,
                markup=True,
                show_time=True,
                show_path=False,
                level=LOG_LEVELS.get(console_level, logging.INFO)
            )
        except ImportError:
            cls._console_handler = logging.StreamHandler(sys.stdout)
            cls._console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
            cls._console_handler.setLevel(LOG_LEVELS.get(console_level, logging.INFO))

        # 创建共享的错误日志处理器（所有 ERROR 级别日志汇总）
        error_file = LOGS_DIR / "error.log"
        cls._error_handler = MaxSizeTimedRotatingFileHandler(
            str(error_file),
            when='midnight',
            backupCount=7,
            maxBytes=50*1024*1024,
            encoding='utf-8'
        )
        cls._error_handler.setLevel(logging.ERROR)
        cls._error_handler.setFormatter(
            logging.Formatter(FILE_FORMAT, datefmt=FILE_DATE_FORMAT)
        )

        # 预创建所有配置的日志器
        for name in cls.LOGGER_CONFIG:
            cls.get_logger(name)

        cls._initialized = True

        # 写入启动标记
        cls._write_startup_marker()

    @classmethod
    def _write_startup_marker(cls):
        """在所有日志文件中写入启动分隔标记"""
        import platform

        marker = f"""
{'='*80}
🚀 SERVER STARTED | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | PID: {os.getpid()}
   Python: {platform.python_version()} | Platform: {platform.system()} {platform.release()}
{'='*80}
"""
        # 写入到所有日志文件
        for config in cls.LOGGER_CONFIG.values():
            log_file = LOGS_DIR / config["file"]
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(marker)
            except Exception:
                pass

        # 也写入到错误日志
        error_file = LOGS_DIR / "error.log"
        try:
            with open(error_file, "a", encoding="utf-8") as f:
                f.write(marker)
        except Exception:
            pass

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取指定名称的日志器

        Args:
            name: 日志器名称，可选值：server, knowledge, docling, rag
                  或任意自定义名称（使用默认配置）

        Returns:
            logging.Logger: 配置好的日志器实例
        """
        if name in cls._loggers:
            return cls._loggers[name]

        # 获取配置（如果是预定义的）
        config = cls.LOGGER_CONFIG.get(name, {
            "file": f"{name}.log",
            "level": "INFO",
            "description": f"Custom logger: {name}"
        })

        # 创建日志器
        logger = logging.getLogger(f"nexus.{name}")
        logger.setLevel(logging.DEBUG)  # 日志器本身设为最低级别，由 handler 控制
        logger.propagate = False  # 防止重复输出

        # 清除已有处理器（防止重复添加）
        logger.handlers.clear()

        # 添加文件处理器
        log_file = LOGS_DIR / config["file"]
        file_handler = MaxSizeTimedRotatingFileHandler(
            str(log_file),
            when='midnight',
            backupCount=7,
            maxBytes=50*1024*1024,
            encoding='utf-8'
        )
        file_handler.setLevel(LOG_LEVELS.get(config["level"], logging.INFO))
        file_handler.setFormatter(
            logging.Formatter(FILE_FORMAT, datefmt=FILE_DATE_FORMAT)
        )
        logger.addHandler(file_handler)

        # 添加控制台处理器（共享）
        if cls._console_handler:
            logger.addHandler(cls._console_handler)

        # 添加错误处理器（共享，ERROR 级别汇总到 error.log）
        if cls._error_handler:
            logger.addHandler(cls._error_handler)

        cls._loggers[name] = logger
        return logger


# 便捷函数：获取各模块日志器
def get_server_logger() -> logging.Logger:
    """获取 server 日志器 - API 请求、启动信息"""
    return LoggerFactory.get_logger("server")

def get_knowledge_logger() -> logging.Logger:
    """获取 knowledge 日志器 - 知识库操作"""
    return LoggerFactory.get_logger("knowledge")

def get_docling_logger() -> logging.Logger:
    """获取 docling_client 日志器 - 调用 Docling API 的请求/响应/耗时"""
    return LoggerFactory.get_logger("docling_client")

def get_rag_logger() -> logging.Logger:
    """获取 rag 日志器 - RAG 底层操作"""
    return LoggerFactory.get_logger("rag")


# 日志装饰器：记录函数执行时间
def log_execution_time(logger_name: str = "server"):
    """
    装饰器：记录函数执行时间

    使用方式：
        @log_execution_time("knowledge")
        def upload_document(...):
            ...
    """
    import functools
    import time

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = LoggerFactory.get_logger(logger_name)
            start_time = time.time()
            func_name = func.__name__

            logger.debug(f"开始执行: {func_name}")
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"执行完成: {func_name} | 耗时: {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"执行失败: {func_name} | 耗时: {duration:.2f}s | 错误: {e}")
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = LoggerFactory.get_logger(logger_name)
            start_time = time.time()
            func_name = func.__name__

            logger.debug(f"开始执行: {func_name}")
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"执行完成: {func_name} | 耗时: {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"执行失败: {func_name} | 耗时: {duration:.2f}s | 错误: {e}")
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator