"""记忆模块入口。

- 短期记忆：SQLite（单库多会话，按 thread_id 隔离）
- 长期记忆：Chroma（本地持久化向量库）

两种记忆都提供统一的 `get` / `save` 方法。
"""

from __future__ import annotations

from typing import Any

from travel_plan_agent.memory.base import (
    DEFAULT_THREAD_ID,
    DEFAULT_USER_ID,
    Memory,
    MemoryRecord,
)
from travel_plan_agent.memory.long_term import ChromaLongTermMemory
from travel_plan_agent.memory.short_term import SQLiteShortTermMemory

__all__ = [
    "DEFAULT_THREAD_ID",
    "DEFAULT_USER_ID",
    "ChromaLongTermMemory",
    "Memory",
    "MemoryRecord",
    "SQLiteShortTermMemory",
    "get_short_memory",
    "get_long_memory",
    "save_short_memory",
    "save_long_memory",
]

_short_memory: SQLiteShortTermMemory | None = None
_long_memory: ChromaLongTermMemory | None = None


def get_short_memory() -> SQLiteShortTermMemory:
    """进程内单例：短期记忆（SQLite）。"""
    global _short_memory
    if _short_memory is None:
        _short_memory = SQLiteShortTermMemory()
    return _short_memory


def get_long_memory() -> ChromaLongTermMemory:
    """进程内单例：长期记忆（Chroma）。"""
    global _long_memory
    if _long_memory is None:
        _long_memory = ChromaLongTermMemory()
    return _long_memory


def save_short_memory(
    content: str,
    *,
    thread_id: str | None = None,
    role: str = "user",
    user_id: str = DEFAULT_USER_ID,
    metadata: dict[str, Any] | None = None,
) -> str:
    """直接写入短期记忆（业务代码可直接调用）。"""
    return get_short_memory().save(
        content, thread_id=thread_id, user_id=user_id, role=role, metadata=metadata
    )


def save_long_memory(
    content: str,
    *,
    thread_id: str | None = None,
    user_id: str = DEFAULT_USER_ID,
    role: str = "user",
    kind: str = "fact",
    metadata: dict[str, Any] | None = None,
) -> str:
    """直接写入长期记忆（业务代码可直接调用）。"""
    meta = {"kind": kind, **(metadata or {})}
    return get_long_memory().save(
        content, thread_id=thread_id, user_id=user_id, role=role, metadata=meta
    )