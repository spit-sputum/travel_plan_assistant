"""短期记忆：SQLite 单文件数据库，按 thread_id 隔离不同会话。

- 所有会话的短期对话都存在**同一个** `.db` 文件里，通过 `thread_id` 列区分；
- `save(content, thread_id=...)` 追加一条消息；
- `get(thread_id=...)` 返回该会话最近 N 条消息（按时间正序）。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from travel_plan_agent.memory.base import (
    DEFAULT_THREAD_ID,
    DEFAULT_USER_ID,
    Memory,
    MemoryRecord,
    now_iso,
)
from travel_plan_agent.memory.paths import resolve_path, short_term_db_path


class SQLiteShortTermMemory(Memory):
    """基于标准库 sqlite3 的短期记忆。"""

    name = "short_term"

    def __init__(
        self,
        db_path: str | Path | None = None,
        max_messages_per_thread: int = 100,
    ) -> None:
        path = resolve_path(db_path) if db_path else short_term_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self.max_messages = max_messages_per_thread
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------ 内部
    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS short_term_messages (
                    id          TEXT PRIMARY KEY,
                    thread_id   TEXT NOT NULL,
                    user_id     TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    metadata    TEXT,
                    created_at  TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_stm_thread "
                "ON short_term_messages (thread_id, id)"
            )
            self._conn.commit()

    # ------------------------------------------------------------- 公共接口
    def save(
        self,
        content: str,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
        role: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """把一条消息写入指定会话（thread_id）。"""
        content = (content or "").strip()
        if not content:
            raise ValueError("短期记忆内容不能为空")
        tid = thread_id or DEFAULT_THREAD_ID
        record_id = uuid.uuid4().hex
        created_at = now_iso()
        meta = dict(metadata or {})
        meta.setdefault("user_id", user_id)
        with self._lock:
            self._conn.execute(
                "INSERT INTO short_term_messages "
                "(id, thread_id, user_id, role, content, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id,
                    tid,
                    user_id,
                    role,
                    content,
                    json.dumps(meta, ensure_ascii=False),
                    created_at,
                ),
            )
            # 只保留该会话最近 max_messages 条，防止无限膨胀
            self._conn.execute(
                "DELETE FROM short_term_messages WHERE thread_id = ? AND id NOT IN ("
                "  SELECT id FROM short_term_messages WHERE thread_id = ? "
                "  ORDER BY created_at DESC, rowid DESC LIMIT ?"
                ")",
                (tid, tid, self.max_messages),
            )
            self._conn.commit()
        return record_id

    def get(
        self,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
        query: str = "",  # 短期记忆按时间检索，query 仅用于可选的关键词过滤
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """读取指定会话最近 limit 条消息，按时间正序返回。"""
        tid = thread_id or DEFAULT_THREAD_ID
        sql = (
            "SELECT id, thread_id, user_id, role, content, metadata, created_at "
            "FROM short_term_messages WHERE thread_id = ?"
        )
        params: list[Any] = [tid]
        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        records = [
            MemoryRecord(
                id=r["id"],
                content=r["content"],
                role=r["role"],
                thread_id=r["thread_id"],
                user_id=r["user_id"],
                created_at=r["created_at"],
                metadata=json.loads(r["metadata"] or "{}"),
            )
            for r in reversed(rows)
        ]
        return records

    def clear(
        self,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
    ) -> int:
        """清空某个会话的短期记忆。"""
        with self._lock:
            if thread_id is None:
                cur = self._conn.execute(
                    "DELETE FROM short_term_messages"
                )  # thread_id为None时清空全部短期记忆
            else:
                cur = self._conn.execute(
                    "DELETE FROM short_term_messages WHERE thread_id = ?", (thread_id,)
                )
            self._conn.commit()
            return cur.rowcount

    # ------------------------------------------------------------- 辅助方法
    def list_threads(self) -> list[str]:
        """返回所有存在短期记忆的 thread_id。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT thread_id FROM short_term_messages ORDER BY thread_id"
            ).fetchall()
        return [r["thread_id"] for r in rows]

    def count(self, thread_id: str | None = None) -> int:
        with self._lock:
            if thread_id is None:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS c FROM short_term_messages"
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS c FROM short_term_messages WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()
        return int(row["c"])  # 这个方法有什么用？返回不同用户相同thread_id的数量吗？

    def close(self) -> None:
        with self._lock:
            self._conn.close()
