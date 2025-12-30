"""
SQLite-based BaseStore implementation for LangGraph long-term memory.

官方 LangGraph 只提供 PostgresStore 和 InMemoryStore。
此模块实现了基于 SQLite 的 BaseStore，用于持久化用户偏好规则（长期记忆）。

复用来源：参考 langgraph.store.postgres.AsyncPostgresStore 接口设计
"""

import aiosqlite
import json
from typing import Optional, Tuple, List, Dict, Any
from langgraph.store.base import BaseStore, Item
from datetime import datetime


class AsyncSQLiteStore(BaseStore):
    """
    SQLite-based implementation of BaseStore for persistent long-term memory.

    用于存储跨对话的持久化数据（如用户偏好规则），独立于 Checkpointer。
    """

    def __init__(self, db_path: str = "store.db"):
        """
        Args:
            db_path: SQLite database file path
        """
        self.db_path = db_path
        self._initialized = False

    async def _ensure_initialized(self):
        """Initialize database schema if not already done."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS langgraph_store (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
            """)
            await db.commit()

        self._initialized = True

    async def aget(self, namespace: Tuple[str, ...], key: str) -> Optional[Item]:
        """
        Get an item from the store.

        Args:
            namespace: Tuple of namespace components (e.g., ("marketing_preferences",))
            key: Item key (e.g., "user_rules")

        Returns:
            Item object with value, or None if not found
        """
        await self._ensure_initialized()

        namespace_str = "/".join(namespace)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value, created_at, updated_at FROM langgraph_store WHERE namespace = ? AND key = ?",
                (namespace_str, key)
            ) as cursor:
                row = await cursor.fetchone()

                if row is None:
                    return None

                value_json, created_at, updated_at = row
                value = json.loads(value_json)

                return Item(
                    value=value,
                    key=key,
                    namespace=namespace,
                    created_at=created_at,
                    updated_at=updated_at
                )

    async def aput(self, namespace: Tuple[str, ...], key: str, value: Dict[str, Any]) -> None:
        """
        Put (upsert) an item into the store.

        Args:
            namespace: Tuple of namespace components
            key: Item key
            value: Dictionary value to store
        """
        await self._ensure_initialized()

        namespace_str = "/".join(namespace)
        value_json = json.dumps(value, ensure_ascii=False)
        now = datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            # Check if exists
            async with db.execute(
                "SELECT created_at FROM langgraph_store WHERE namespace = ? AND key = ?",
                (namespace_str, key)
            ) as cursor:
                row = await cursor.fetchone()

            if row is None:
                # Insert new
                await db.execute(
                    "INSERT INTO langgraph_store (namespace, key, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (namespace_str, key, value_json, now, now)
                )
            else:
                # Update existing (preserve created_at)
                await db.execute(
                    "UPDATE langgraph_store SET value = ?, updated_at = ? WHERE namespace = ? AND key = ?",
                    (value_json, now, namespace_str, key)
                )

            await db.commit()

    async def adelete(self, namespace: Tuple[str, ...], key: str) -> None:
        """
        Delete an item from the store.

        Args:
            namespace: Tuple of namespace components
            key: Item key
        """
        await self._ensure_initialized()

        namespace_str = "/".join(namespace)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM langgraph_store WHERE namespace = ? AND key = ?",
                (namespace_str, key)
            )
            await db.commit()

    async def asearch(self, namespace: Tuple[str, ...]) -> List[Item]:
        """
        List all items in a namespace.

        Args:
            namespace: Tuple of namespace components

        Returns:
            List of Item objects
        """
        await self._ensure_initialized()

        namespace_str = "/".join(namespace)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT key, value, created_at, updated_at FROM langgraph_store WHERE namespace = ?",
                (namespace_str,)
            ) as cursor:
                rows = await cursor.fetchall()

                items = []
                for key, value_json, created_at, updated_at in rows:
                    value = json.loads(value_json)
                    items.append(Item(
                        value=value,
                        key=key,
                        namespace=namespace,
                        created_at=created_at,
                        updated_at=updated_at
                    ))

                return items

    async def abatch(self, operations: List[Tuple[str, Tuple[str, ...], str, Optional[Dict[str, Any]]]]) -> List[Optional[Item]]:
        """
        Batch operations for efficiency.

        Args:
            operations: List of (op, namespace, key, value?) tuples
                op can be 'get', 'put', 'delete'

        Returns:
            List of results (Item for get, None for put/delete)
        """
        results = []
        for operation in operations:
            op = operation[0]
            namespace = operation[1]
            key = operation[2]

            if op == "get":
                result = await self.aget(namespace, key)
                results.append(result)
            elif op == "put":
                value = operation[3]
                await self.aput(namespace, key, value)
                results.append(None)
            elif op == "delete":
                await self.adelete(namespace, key)
                results.append(None)
            else:
                raise ValueError(f"Unknown operation: {op}")

        return results

    def batch(self, operations: List[Tuple[str, Tuple[str, ...], str, Optional[Dict[str, Any]]]]) -> List[Optional[Item]]:
        """
        Synchronous batch operations (not recommended, use abatch).

        Raises NotImplementedError as this is an async-only store.
        """
        raise NotImplementedError("Use abatch() instead for async operations")
