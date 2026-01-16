
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
    
    # Search
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    USE_TAVILY = os.getenv("USE_TAVILY", "false").lower() == "true"
    
    # Paths
    AUDIT_LOG_PATH = LOGS_DIR / "audit.jsonl"
    
settings = Settings()
