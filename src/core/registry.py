from typing import Dict, List, Optional, Any
from .capability import CapabilitySchema
# Avoid circular import by using forward reference or TYPE_CHECKING if needed
# But here we just need to store objects, we don't necessarily need to import BaseTeacher at runtime if we type hint loosely or use string names.
# However, for register(teacher), we'd like type safety.
# Let's import BaseTeacher inside methods or use Any for now to avoid circular dependency if BaseTeacher imports this.
# Actually, BaseTeacher won't import Registry. Registry imports BaseTeacher.
# But BaseTeacher is in src.teachers.base.
# Let's use Any for the teacher object to be safe, or import inside if needed.

class TeacherRegistry:
    _instance = None
    
    def __init__(self):
        self._teachers: Dict[str, Any] = {}
        self._capabilities: Dict[str, CapabilitySchema] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TeacherRegistry()
        return cls._instance

    def register(self, teacher: Any):
        """
        Register a teacher instance.
        The teacher must have a capability() method.
        """
        if not hasattr(teacher, "capability"):
            raise ValueError(f"Teacher {teacher} must implement capability()")
        
        cap = teacher.capability()
        name = cap["name"]
        
        self._teachers[name] = teacher
        self._capabilities[name] = cap
        print(f"[Registry] Registered teacher: {name}")

    def get_all_capabilities(self) -> List[CapabilitySchema]:
        return list(self._capabilities.values())

    def find_capable_teacher(self, user_request: str, prd_context: Dict[str, Any]) -> Optional[str]:
        """
        Find the best matching teacher for the request.
        For now, simple keyword matching against 'supported_tasks' and 'description'.
        In a real system, this would use semantic search or LLM routing.
        """
        user_request_lower = user_request.lower()
        
        best_match = None
        max_score = 0
        
        for name, cap in self._capabilities.items():
            score = 0
            
            # Check supported tasks
            for task in cap["supported_tasks"]:
                # Exact match or substring match (task in request)
                if task.lower() in user_request_lower:
                    score += 10
                # Reverse match (request words in task) - simplified
                # e.g. "refund" in "refund_policy"
                elif any(word in task.lower() for word in user_request_lower.split() if len(word) > 3):
                     # Lower score for partial match
                     score += 2
            
            # Check description keywords (simple heuristic)
            # This is a placeholder for more complex logic
            if name.lower() in user_request_lower:
                score += 5
                
            if score > max_score:
                max_score = score
                best_match = name
                
        if max_score > 0:
            return best_match
            
        return None
