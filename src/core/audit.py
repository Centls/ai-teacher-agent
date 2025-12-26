import json
import time
from pathlib import Path
from typing import Any, Dict
from config.settings import settings

class AuditLogger:
    def __init__(self, log_path: Path = settings.AUDIT_LOG_PATH):
        self.log_path = log_path

    def log_event(self, event_type: str, session_id: str, details: Dict[str, Any]):
        """
        Log an audit event in JSONL format.
        """
        # Determine LLM Mode
        llm_mode = "mock" if "placeholder" in settings.OPENAI_API_KEY or not settings.OPENAI_API_KEY else "real"
        
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "session_id": session_id,
            "teacher": details.get("teacher", "system"),
            "node": details.get("node", "unknown"),
            "status": details.get("status", "UNKNOWN"),
            "llm_mode": llm_mode,
            "latency_ms": details.get("duration_ms", 0),
            "prd_compliance": details.get("prd_compliance", "UNKNOWN"),
            "details": details # Keep full details nested
        }
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_node_execution(self, session_id: str, node_name: str, inputs: Any, outputs: Any, duration: float):
        # Infer teacher from node name (convention: teacher_node)
        teacher = node_name.split("_")[0] if "_" in node_name else "system"
        
        # Extract status if available
        status = "SUCCESS"
        if isinstance(outputs, dict):
            status = outputs.get("status", "SUCCESS")
            
        self.log_event("node_execution", session_id, {
            "teacher": teacher,
            "node": node_name,
            "status": status,
            "duration_ms": round(duration * 1000, 2),
            "inputs": str(inputs)[:1000], 
            "outputs": str(outputs)[:1000],
            "prd_compliance": outputs.get("prd_compliance", "UNKNOWN") if isinstance(outputs, dict) else "UNKNOWN"
        })

audit_logger = AuditLogger()
