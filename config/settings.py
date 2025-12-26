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
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-placeholder")
    DEFAULT_MODEL = "gpt-4o"
    AUDIT_LOG_PATH = LOGS_DIR / "audit.jsonl"
    
settings = Settings()
