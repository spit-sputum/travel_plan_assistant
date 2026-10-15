"""travel_plan_agent：基于 LangChain / LangGraph 的 AI 旅行规划助手。

最简用法：
    from travel_plan_agent import build_agent

    agent = build_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "帮我规划北京三日游"}]},
        config={"configurable": {"thread_id": "user-001"}},
    )
    print(result["messages"][-1].content)
"""

from travel_plan_agent.build_agent import build_agent
from travel_plan_agent.config import BASE_DIR, Settings, get_settings
from travel_plan_agent.model import get_model

__version__ = "0.1.1"

__all__ = [
    "BASE_DIR",
    "Settings",
    "__version__",
    "build_agent",
    "get_model",
    "get_settings",
]
