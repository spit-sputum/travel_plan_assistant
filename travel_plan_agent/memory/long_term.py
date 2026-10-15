"""长期记忆：Chroma 向量库（本地持久化，无需启动任何服务）。

- 按 `user_id` 隔离集合（同一用户的所有会话共享长期记忆）；
- `save(content, ...)` 写入一条语义化记忆，自动生成向量；
- `get(query=...)` 按语义相似度检索，`query` 为空时返回最近写入的若干条。
"""

from __future__ import annotations

import hashlib
import logging
import re
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
from travel_plan_agent.memory.embeddings import get_embedding_function
from travel_plan_agent.memory.paths import (
    long_term_collection_name,
    long_term_db_dir,
    resolve_path,
)

logger = logging.getLogger(__name__)

_CHROMA_META_TYPES = (str, int, float, bool)


def _sanitize(name: str) -> str:
    """生成合法的 Chroma 集合名后缀（非 ASCII 字符用哈希替代，保证唯一且合法）。"""
    cleaned = re.sub(r"[^0-9a-zA-Z_-]", "_", name or "")[:64]
    digest = hashlib.blake2b((name or "").encode("utf-8"), digest_size=4).hexdigest()
    return f"{cleaned.strip('_-') or 'user'}_{digest}"


def _legal_collection_name(name: str) -> str:
    """Chroma 集合名要求：3-512 个字符，首尾必须是字母或数字。"""
    cleaned = re.sub(r"[^0-9a-zA-Z_-]", "_", name or "").strip("_-")
    if not cleaned or not cleaned[0].isalnum():
        cleaned = f"c{cleaned}"
    if not cleaned[-1].isalnum():
        cleaned = f"{cleaned}0"
    return cleaned[:400]


class ChromaLongTermMemory(Memory):
    """基于 Chroma 的长期记忆。"""

    name = "long_term"

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        collection_name: str | None = None,
        embedding_function: Any | None = None,
    ) -> None:
        path = resolve_path(persist_dir) if persist_dir else long_term_db_dir()
        path.mkdir(parents=True, exist_ok=True)
        self.persist_dir = str(path)
        self.collection_name = _legal_collection_name(
            collection_name or long_term_collection_name()
        )
        self.embedding_function = embedding_function or get_embedding_function()
        self._client: Any | None = None
        self._collections: dict[str, Any] = {}

    # ------------------------------------------------------------------ 内部
    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                from chromadb.config import Settings as ChromaSettings

                import chromadb
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "缺少安装包 chromadb，请先执行：pip install chromadb"
                ) from exc
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )
        return self._client

    def _collection(self, user_id: str) -> Any:
        key = _sanitize(user_id)
        if key not in self._collections:
            self._collections[key] = self.client.get_or_create_collection(
                name=f"{self.collection_name}__{key}",
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine", "user_id": user_id},
            )
        return self._collections[key]

    @staticmethod
    def _clean_metadata(meta: dict[str, Any]) -> dict[str, Any]:
        """Chroma 不接受 None / 复杂类型，这里统一过滤。"""
        return {str(k): v for k, v in meta.items() if isinstance(v, _CHROMA_META_TYPES)}

    @staticmethod
    def _build_where(
        thread_id: str | None, scope: str, kind: str | None
    ) -> dict[str, Any] | None:  # 构造查询语句
        conds: list[dict[str, Any]] = []
        if scope == "thread" or (scope == "auto" and thread_id):
            conds.append({"thread_id": thread_id or DEFAULT_THREAD_ID})
        if kind:
            conds.append({"kind": kind})
        if not conds:
            return None
        return conds[0] if len(conds) == 1 else {"$and": conds}

    @staticmethod
    def _to_record(
        doc: str,
        meta: dict[str, Any] | None,
        record_id: str,
        score: float | None = None,
    ) -> MemoryRecord:
        meta = meta or {}
        return MemoryRecord(
            id=record_id,
            content=doc,
            role=str(meta.get("role", "user")),
            thread_id=meta.get("thread_id"),
            user_id=str(meta.get("user_id", DEFAULT_USER_ID)),
            score=score,
            created_at=str(meta.get("created_at", "")),
            metadata={
                k: v
                for k, v in meta.items()
                if k not in {"role", "thread_id", "user_id"}
            },
        )

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
        """把一条值得长期记住的信息写入向量库。"""
        content = (content or "").strip()
        if not content:
            raise ValueError("长期记忆内容不能为空")
        record_id = uuid.uuid4().hex
        meta = self._clean_metadata(
            {
                **(metadata or {}),
                "user_id": user_id,
                "thread_id": thread_id or DEFAULT_THREAD_ID,
                "role": role,
                "kind": (metadata or {}).get("kind", "fact"),
                "created_at": now_iso(),
            }
        )
        self._collection(user_id).add(
            ids=[record_id], documents=[content], metadatas=[meta]
        )
        return record_id

    def get(
        self,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
        query: str = "",
        limit: int = 5,
        kind: str | None = None,
        scope: str = "auto",
    ) -> list[MemoryRecord]:
        """按语义检索长期记忆。

        scope: `thread` 仅当前会话，`user` 全部会话（默认 `auto`：传了 thread_id 就限本会话）。
        """
        collection = self._collection(user_id)
        where = self._build_where(thread_id, scope, kind)
        n = max(1, int(limit))
        if query.strip():
            resp = collection.query(
                query_texts=[query.strip()],
                n_results=n,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            docs = list((resp.get("documents") or [[]])[0] or [])
            metas = list((resp.get("metadatas") or [[]])[0] or [])
            dists = list((resp.get("distances") or [[]])[0] or [])
            ids = list((resp.get("ids") or [[]])[0] or [])
            results: list[MemoryRecord] = []
            for i, doc in enumerate(docs):
                meta = metas[i] if i < len(metas) else None
                dist = float(dists[i]) if i < len(dists) else None
                results.append(
                    self._to_record(
                        doc,
                        meta,
                        ids[i] if i < len(ids) else "",
                        score=None if dist is None else round(1.0 - dist, 4),
                    )
                )
            return results
        resp = collection.get(where=where, limit=n, include=["documents", "metadatas"])
        return [
            self._to_record(doc, meta, rid)
            for rid, doc, meta in zip(
                resp.get("ids") or [],
                resp.get("documents") or [],
                resp.get("metadatas") or [],
            )
        ]

    def clear(
        self,
        *,
        thread_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
    ) -> int:
        collection = self._collection(user_id)
        before = collection.count()
        if thread_id is None:
            all_ids = collection.get(include=[]).get("ids") or []
            if all_ids:
                collection.delete(ids=all_ids)
        else:
            collection.delete(where={"thread_id": thread_id or DEFAULT_THREAD_ID})
        return int(before - collection.count())

    # ------------------------------------------------------------- 辅助方法
    def count(self, user_id: str = DEFAULT_USER_ID) -> int:
        return int(self._collection(user_id).count())

    def list_items(
        self, user_id: str = DEFAULT_USER_ID, limit: int = 50
    ) -> list[MemoryRecord]:
        return self.get(user_id=user_id, query="", limit=limit)
