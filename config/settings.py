import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
PROMPTS_DIR = CONFIG_DIR / "prompts"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

class Settings:
    # API Keys (Robust loading: LLM_API_KEY > DEEPSEEK_API_KEY > OPENAI_API_KEY)
    OPENAI_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "sk-placeholder"
    OPENAI_API_BASE = os.getenv("LLM_API_BASE") or os.getenv("DEEPSEEK_API_BASE") or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
    
    # Models
    DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
    
    # Search
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    USE_TAVILY = os.getenv("USE_TAVILY", "false").lower() == "true"
    
    # Paths
    AUDIT_LOG_PATH = LOGS_DIR / "audit.jsonl"
    
settings = Settings()
