import yaml
from pathlib import Path
from typing import Dict, Any
from config.settings import PROMPTS_DIR

class PromptManager:
    _cache: Dict[str, Any] = {}

    @classmethod
    def load(cls, prompt_name: str, version: str = "latest") -> Dict[str, Any]:
        """
        Load a prompt by name (e.g., 'supervisor', 'teachers/marketing/v1.0').
        """
        # Simple cache implementation (in real world, handle cache invalidation)
        cache_key = f"{prompt_name}:{version}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        if prompt_name.endswith(".yaml"):
            prompt_name = prompt_name[:-5]

        # Construct path
        # If version is specified and not latest, look for specific file
        # For simplicity in this skeleton, we assume prompt_name maps to a file relative to PROMPTS_DIR
        
        path = PROMPTS_DIR / f"{prompt_name}.yaml"
        
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        cls._cache[cache_key] = data
        return data

    @classmethod
    def get_template(cls, prompt_name: str) -> str:
        data = cls.load(prompt_name)
        return data.get("instructions", "")
