"""记忆模块的统一抽象接口。

设计目标：
- 短期记忆（SQLite）与长期记忆（Chroma）遵循同一套 `get` / `save` 方法签名，
  上层（Agent 工具、业务代码）无需关心底层存储差异。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

DEFAULT_USER_ID = "default_user"
DEFAULT_THREAD_ID = "default_thread"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(slots=True)
class MemoryRecord:
    """一条记忆记录（短期 / 长期通用）。"""

    id: str
    content: str
    role: str = "user"
    thread_id: str | None = None
    user_id: str = DEFAULT_USER_ID
    score: float | None = None
    created_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "score": self.score,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class Memory(ABC):
    """记忆存储接口：必须实现 `save`（写入）与 `get`（读取）。"""

    name: str = "memory"

    @abstractmethod
    def save(
        self,
        content: str,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
        role: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """写入一条记忆，返回记录 ID。"""

    @abstractmethod
    def get(
        self,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
        query: str = "",
        limit: int = 5,
    ) -> list[MemoryRecord]:
        """读取记忆。短期记忆按时间倒序取最近若干条，长期记忆按语义相似度检索。"""

    def clear(
        self,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
    ) -> int:
        """清空记忆，返回删除条数。"""
        raise NotImplementedError(f"{type(self).__name__} 未实现 clear()")