
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# =============================================================================
# Global Model Configuration (Must be set before importing heavy libraries)
# =============================================================================
# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

# Set HuggingFace Cache Directory to project_root/models/huggingface
# This ensures all downloaded models are stored locally in the project
MODELS_DIR = PROJECT_ROOT / "models"
os.environ["HF_HOME"] = str(MODELS_DIR / "huggingface")
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com" # Use China mirror for speed

class Settings:
    """
    Application Settings
    """
    # Project Paths
    BASE_DIR = PROJECT_ROOT
    CONFIG_DIR = BASE_DIR / "config"
    PROMPTS_DIR = CONFIG_DIR / "prompts"
    LOGS_DIR = BASE_DIR / "logs"
    DATA_DIR = BASE_DIR / "data"

    # Ensure logs directory exists
    LOGS_DIR.mkdir(exist_ok=True)
    # API Keys (Robust loading: LLM_API_KEY > DEEPSEEK_API_KEY > OPENAI_API_KEY)
    OPENAI_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "sk-placeholder"
    OPENAI_API_BASE = os.getenv("LLM_API_BASE") or os.getenv("DEEPSEEK_API_BASE") or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
    
    # Models
    DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
    
    # Embedding Configuration
    # Provider: 'openai' (default) or 'local' (HuggingFace)
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    # Model Name:
    # - OpenAI: 'text-embedding-3-small', 'text-embedding-v2' (Aliyun)
    # - Local: 'BAAI/bge-small-zh-v1.5', 'BAAI/bge-m3'
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Reranker Configuration
    # 使用 sentence-transformers CrossEncoder 进行重排序
    # Model: 'BAAI/bge-reranker-v2-m3' (推荐，多语言支持)
    RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
    RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    RERANKER_MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "512"))
    # 设备：auto（自动检测）/ cpu / cuda / mps
    RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "auto")

    # Parent-Child Index Configuration (父子索引)
    # 依赖：langchain_classic.retrievers.ParentDocumentRetriever
    # 使用小块检索，返回大块上下文
    PARENT_CHILD_ENABLED = os.getenv("PARENT_CHILD_ENABLED", "true").lower() == "true"
    # 父块大小（返回给 LLM 的上下文大小）
    PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", "2000"))
    PARENT_CHUNK_OVERLAP = int(os.getenv("PARENT_CHUNK_OVERLAP", "200"))
    # 子块大小（用于向量检索的精确匹配）
    CHILD_CHUNK_SIZE = int(os.getenv("CHILD_CHUNK_SIZE", "300"))
    CHILD_CHUNK_OVERLAP = int(os.getenv("CHILD_CHUNK_OVERLAP", "30"))
    # DocStore 存储路径（存储父块原文）
    DOCSTORE_PATH = DATA_DIR / "parent_docstore"

    # Semantic Chunking Configuration (语义分块)
    # 依赖：chonkie.SemanticChunker（完整复用）
    # 用于父块的语义分割，替代固定大小分块
    SEMANTIC_CHUNKING_ENABLED = os.getenv("SEMANTIC_CHUNKING_ENABLED", "true").lower() == "true"
    # 语义分块 embedding 模型
    # 默认使用项目 Embedding 模型 BAAI/bge-large-zh-v1.5（中文优化，与检索 embedding 一致）
    # 模型文件存储在 models/huggingface 目录下（通过 HF_HOME 环境变量控制）
    SEMANTIC_EMBEDDING_MODEL = os.getenv("SEMANTIC_EMBEDDING_MODEL", "auto")
    # 相似度百分位阈值（85-95 推荐，越高分块越细）
    SEMANTIC_SIMILARITY_PERCENTILE = float(os.getenv("SEMANTIC_SIMILARITY_PERCENTILE", "85.0"))
    # 语义块目标大小（字符数，用于合并小块）
    SEMANTIC_CHUNK_SIZE = int(os.getenv("SEMANTIC_CHUNK_SIZE", "2000"))
    
    # Search
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    USE_TAVILY = os.getenv("USE_TAVILY", "false").lower() == "true"
    
    # Paths
    AUDIT_LOG_PATH = LOGS_DIR / "audit.jsonl"
    
settings = Settings()
