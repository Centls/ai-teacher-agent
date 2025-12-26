from pathlib import Path
from typing import Dict, Optional, Any
import yaml
from config.settings import DATA_DIR

class PRDManager:
    _cache: Dict[str, str] = {}
    PRD_DIR = DATA_DIR / "prd"

    @classmethod
    def load(cls, prd_name: str) -> Dict[str, Any]:
        """
        Load PRD content by name and parse it into a structured dictionary.
        Supports .md and .yaml files.
        """
        if prd_name in cls._cache:
            return cls._cache[prd_name]

        # Try YAML first
        yaml_path = cls.PRD_DIR / f"{prd_name}.yaml"
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                parsed_content = yaml.safe_load(f)
                cls._cache[prd_name] = parsed_content
                return parsed_content

        # Try Markdown
        md_path = cls.PRD_DIR / f"{prd_name}.md"
        if not md_path.exists():
            print(f"Warning: PRD file {md_path} not found.")
            return {}

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        parsed_content = cls.parse(content)
        cls._cache[prd_name] = parsed_content
        return parsed_content

    @staticmethod
    def parse(content: str) -> Dict[str, Any]:
        """
        Simple Markdown Parser to extract headers and bullet points.
        Returns a nested dictionary.
        """
        result = {}
        current_section = "general"
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('# '):
                # Title, ignore or store as meta
                continue
            elif line.startswith('## '):
                current_section = line[3:].strip().lower().replace(' ', '_')
                result[current_section] = []
            elif line.startswith('- ') or line.startswith('* '):
                item = line[2:].strip()
                if current_section not in result:
                    result[current_section] = []
                # If result[current_section] is a list, append
                if isinstance(result[current_section], list):
                    result[current_section].append(item)
            elif line.startswith('  - ') or line.startswith('  * '):
                 # Nested item, simple handling: append to last item or keep flat
                 pass 
                 
        return result

    @classmethod
    def get_system_constraints(cls) -> Dict[str, Any]:
        return cls.load("system_prd")
