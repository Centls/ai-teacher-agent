import json
import os
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple

class JSONLCheckpointSaver:
    """
    A checkpoint saver that stores checkpoints in a JSONL file.
    """
    def __init__(self, serde=None, base_path: str = "logs/checkpoints"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _get_file_path(self, thread_id: str) -> str:
        return os.path.join(self.base_path, f"{thread_id}.jsonl")

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get a checkpoint tuple from the storage."""
        # print(f"[Checkpoint] get_tuple called. Config type: {type(config)}")
        if not isinstance(config, dict):
            # print(f"[Checkpoint] Config is not a dict: {type(config)}")
            return None

        try:
            thread_id = config["configurable"]["thread_id"]
            file_path = self._get_file_path(thread_id)
            
            if not os.path.exists(file_path):
                return None
                
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    return None
                
                # Get the last line (latest checkpoint)
                last_line = lines[-1]
                data = json.loads(last_line)
                
                # Reconstruct Checkpoint and Metadata
                checkpoint: Checkpoint = data["checkpoint"]
                metadata: CheckpointMetadata = data["metadata"]
                parent_config = data.get("parent_config")
                
                return CheckpointTuple(
                    config=config,
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=parent_config
                )
        except Exception as e:
            print(f"[Checkpoint] Error getting tuple: {e}")
            return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints."""
        # Simplified implementation: just return the latest if config is provided
        if config:
            tpl = self.get_tuple(config)
            if tpl:
                yield tpl

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """Save a checkpoint to the storage."""
        try:
            # Debug prints
            # print(f"[Checkpoint] Saving. Config type: {type(config)}")
            # print(f"[Checkpoint] Config: {config}")
            
            # Simple check to avoid the error
            if not isinstance(config, dict):
                print(f"[Checkpoint] Config is not a dict: {type(config)}")
                return config

            thread_id = config["configurable"]["thread_id"]
            file_path = self._get_file_path(thread_id)
            
            data = {
                "config": config,
                "checkpoint": checkpoint,
                "metadata": metadata,
                "parent_config": config, # Simplified
                "timestamp": str(metadata.get("ts") if metadata else "")
            }
            
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, default=str) + "\n")
                
        except Exception as e:
            print(f"[Checkpoint] Error saving checkpoint: {e}")
            # import traceback
            # traceback.print_exc()
            
        return config

    # Async methods (required by abstract base class, can just delegate or pass)
    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.get_tuple(config)

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Save intermediate writes (not implemented for JSONL, but required by interface)."""
        pass

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        pass
