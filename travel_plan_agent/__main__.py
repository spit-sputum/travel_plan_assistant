"""单命令启动入口：python -m travel_plan_agent

分发场景下对方只需要 Python 环境：
    pip install -r requirements.txt
    python -m travel_plan_agent
然后浏览器打开 http://127.0.0.1:8000 即是完整界面（前端已由后端托管）。

可用环境变量覆盖：
    TRAVEL_PLAN_HOST  监听地址，默认 127.0.0.1
    TRAVEL_PLAN_PORT  监听端口，默认 8000
"""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    host = os.getenv("TRAVEL_PLAN_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("TRAVEL_PLAN_PORT", "8000"))

    print()
    print("  AI 旅行规划助手")
    print(f"  界面与接口：http://{host}:{port}")
    print(f"  接口文档：  http://{host}:{port}/docs")
    print("  停止服务：  Ctrl + C")
    print()

    # 内部使用全局单例 + SQLite，必须单进程运行
    uvicorn.run("travel_plan_agent.server:app", host=host, port=port, workers=1)


if __name__ == "__main__":
    main()
