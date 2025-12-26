import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

class Settings(BaseModel):
    """
    Centralized configuration for the application.
    """
    # Base Paths
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    
    @property
    def CONFIG_DIR(self) -> Path:
        return self.BASE_DIR / "config"
    
    @property
    def LOGS_DIR(self) -> Path:
        path = self.BASE_DIR / "logs"
        path.mkdir(exist_ok=True)
        return path
        
    @property
    def DATA_DIR(self) -> Path:
        path = self.BASE_DIR / "data"
        path.mkdir(exist_ok=True)
        return path

    # OpenAI
    OPENAI_API_KEY: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    DEFAULT_MODEL: str = Field(default="gpt-4o")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    
    # Database (Future)
    # DB_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./nexus.db"))

    model_config = {
        "arbitrary_types_allowed": True
    }

settings = Settings()
