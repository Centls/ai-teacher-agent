from typing import Dict, Any

class MemoryManager:
    """
    Manages different layers of memory (Session, Global, Tool).
    """
    
    def __init__(self):
        self.local_memory = {}
        
    def get_context(self, user_id: str) -> Dict[str, Any]:
        return self.local_memory.get(user_id, {})
        
    def update_context(self, user_id: str, data: Dict[str, Any]):
        if user_id not in self.local_memory:
            self.local_memory[user_id] = {}
        self.local_memory[user_id].update(data)
