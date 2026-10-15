"""Agent 与记忆的进程内单例、配置校验与启动预热。

要点：
- Agent 只构建一次（模型、工具、checkpointer 全部复用），避免每个请求重建。
- 启动时预热嵌入模型，避免第一个用户的第一次对话卡顿。
- **配置缺失时服务仍能启动**（便于对方先看到界面再填 Key），
  只在真正调用对话接口时返回清晰的中文提示。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from travel_plan_agent.build_agent import build_agent
from travel_plan_agent.config import get_settings
from travel_plan_agent.memory import get_long_memory

logger = logging.getLogger(__name__)

_ready = False  # Agent 是否已成功构建（供健康检查展示）


def config_error() -> str | None:
    """检查必要配置；返回人类可读的错误说明，None 表示配置正常。"""
    settings = get_settings()
    if not settings.model_api_key.get_secret_value().strip():
        return (
            "未配置大模型密钥：请把 travel_plan_agent/.env.example 复制为 "
            "travel_plan_agent/.env，并填写 MODEL_API_KEY（以及需要用到工具的 "
            "TAVILY_API_KEY / GAODE_KEY / HEFENG_KEY）"
        )
    return None


@lru_cache(maxsize=1)
def get_agent() -> Any:
    """全局单例：整个服务只构建一个 Agent。"""
    return build_agent()


def require_agent() -> Any:
    """获取 Agent；配置缺失或构建失败时抛出带中文说明的异常。"""
    error = config_error()
    if error:
        raise RuntimeError(error)
    try:
        return get_agent()
    except Exception as exc:  # noqa: BLE001 - 统一转换成可读提示
        raise RuntimeError(f"Agent 初始化失败：{exc}") from exc


def agent_ready() -> bool:
    """Agent 是否已就绪（供 /health 展示）。"""
    return _ready


def warmup() -> bool:
    """启动预热：构建 Agent 并加载嵌入模型。

    失败不阻断服务启动 —— 这样对方没填 Key 也能先打开界面。
    """
    global _ready
    error = config_error()
    if error:
        logger.warning("跳过 Agent 预热：%s", error)
        return False
    try:
        get_agent()
    except Exception as exc:  # noqa: BLE001 - 预热失败不应阻断启动
        logger.warning("Agent 预热失败：%s", exc)
        return False

    try:
        # 触发 sentence-transformers 首次加载；模型缺失会自动降级为哈希嵌入
        get_long_memory().get(query="预热", user_id="__warmup__", limit=1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("嵌入模型预热失败（不影响启动）：%s", exc)

    _ready = True
    return True
