"""Agent 与记忆的进程内单例、启动预热。

要点：
- Agent 只构建一次（模型、工具、checkpointer 全部复用），避免每个请求重建。
- 启动时预热嵌入模型，避免第一个用户的第一次对话卡顿。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from travel_plan_agent.build_agent import build_agent
from travel_plan_agent.memory import get_long_memory


@lru_cache(maxsize=1)
def get_agent() -> Any:
    """全局单例：整个服务只构建一个 Agent。"""
    return build_agent()


def warmup() -> None:
    """启动预热：提前构建 Agent 并触发嵌入模型加载（约 1~2 秒）。"""
    get_agent()
    try:
        # 触发 sentence-transformers 首次加载；失败不影响服务启动
        get_long_memory().get(query="预热", user_id="__warmup__", limit=1)
    except Exception:  # noqa: BLE001 - 预热失败不应阻断服务
        pass
