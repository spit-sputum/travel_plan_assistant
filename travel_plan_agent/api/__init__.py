"""HTTP 接口层（FastAPI）：把 Agent 内核包装成前端可直接调用的服务。

- schemas.py：请求 / 响应模型（前端契约）
- deps.py：Agent 单例与启动预热
- chat.py：对话、流式、会话列表 / 历史 / 删除
"""

from travel_plan_agent.api.chat import router as chat_router

__all__ = ["chat_router"]
