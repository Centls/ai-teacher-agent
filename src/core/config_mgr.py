from typing import Any
from .prompt_mgr import PromptManager

class ConfigManager:
    """
    Manages dynamic configuration and hot-reloading.
    """
    
    @staticmethod
    def get_prompt(name: str) -> str:
        return PromptManager.get_template(name)

    @staticmethod
    def reload_config():
        # Clear caches to force reload
        PromptManager._cache.clear()
        print("Configuration reloaded.")
