"""从 LangChain / LangGraph 的 ToolRuntime 中解析会话标识（thread_id / user_id）。"""

from __future__ import annotations

from typing import Any

from travel_plan_agent.memory.base import DEFAULT_THREAD_ID, DEFAULT_USER_ID


def _lookup(runtime: Any, key: str) -> str | None:
    """依次从 context、config.configurable、state 中查找 key。"""
    context = getattr(runtime, "context", None)
    if isinstance(context, dict) and context.get(key):
        return str(context[key])

    config = getattr(runtime, "config", None)
    if isinstance(config, dict):
        configurable = config.get("configurable") or {}
        if isinstance(configurable, dict) and configurable.get(key):
            return str(configurable[key])

    state = getattr(runtime, "state", None)
    if isinstance(state, dict) and state.get(key):
        return str(state[key])

    return None


def resolve_thread_id(runtime: Any, default: str = DEFAULT_THREAD_ID) -> str:
    """获取当前会话的 thread_id（短期记忆的隔离键）。"""
    return _lookup(runtime, "thread_id") or default


def resolve_user_id(runtime: Any, default: str = DEFAULT_USER_ID) -> str:
    """获取当前用户 id（长期记忆的隔离键）。"""
    return _lookup(runtime, "user_id") or default