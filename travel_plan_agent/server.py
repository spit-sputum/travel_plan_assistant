"""FastAPI 服务入口：把 travel_plan_agent 暴露成前端可调用的 HTTP 接口。

两种启动方式：

1. 分发 / 日常使用（前后端一体，只需 Python）：
       python -m travel_plan_agent
   浏览器打开 http://127.0.0.1:8000 即是界面（需已构建前端到 webui/）

2. 开发（前后端分离，前端热更新）：
       uvicorn travel_plan_agent.server:app --host 127.0.0.1 --port 8000
   前端在 travel-plan-web 目录另行 `npm run dev`

接口文档：http://127.0.0.1:8000/docs
注意：内部使用全局单例与 SQLite，请以单进程运行（不要 --workers > 1）。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from travel_plan_agent import __version__
from travel_plan_agent.api import chat_router
from travel_plan_agent.api.deps import agent_ready, config_error, warmup
from travel_plan_agent.api.schemas import ApiResponse
from travel_plan_agent.config import get_settings
from travel_plan_agent.tools.all_tools import ALL_TOOLS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动预热：构建 Agent + 加载嵌入模型。

    放进线程执行，避免长时间阻塞事件循环导致启动探测超时。
    """
    await asyncio.to_thread(warmup)
    yield


app = FastAPI(
    title="Travel Plan Agent API",
    description="AI 旅行规划助手后端接口",
    version=__version__,
    lifespan=lifespan,
)

# 本地开发放行前端来源；本服务无鉴权，故不启用凭证
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["system"])
def health() -> dict:
    """健康检查 + 基本信息。"""
    settings = get_settings()
    return ApiResponse(
        data={
            "status": "ok",
            "version": __version__,
            "agentReady": agent_ready(),
            "configIssue": config_error(),
            "provider": settings.model_provider,
            "model": settings.model_name or "(该供应商默认模型)",
            "tools": len(ALL_TOOLS),
        }
    ).model_dump()


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """浏览器会自动请求图标，返回 204 避免日志里刷 404。"""
    return Response(status_code=204)


# --------------------------------------------------------------- 前端静态资源
# 构建：cd travel-plan-web && npm run build:agent
# 产物落到 travel_plan_agent/webui/，由后端直接托管 —— 分发时对方无需 Node.js。
WEBUI_DIR = (Path(__file__).resolve().parent / "webui").resolve()

if (WEBUI_DIR / "index.html").is_file():
    _assets_dir = WEBUI_DIR / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """SPA 回退：非 /api 路径统一返回 index.html。

        注意：该通配路由必须最后注册，否则会吞掉 /api、/docs 等接口。
        """
        target = (WEBUI_DIR / full_path).resolve()
        # 仅允许返回 webui 目录内的真实文件，防止路径穿越
        if full_path and target.is_file() and target.is_relative_to(WEBUI_DIR):
            return FileResponse(target)
        return FileResponse(WEBUI_DIR / "index.html")

else:

    @app.get("/", include_in_schema=False)
    def root() -> HTMLResponse:
        """未构建前端时的友好提示。"""
        return HTMLResponse(
            """
            <html lang="zh-CN"><head><meta charset="utf-8">
            <title>Travel Plan Agent API</title></head>
            <body style="font-family:system-ui;padding:32px;line-height:1.9">
              <h2 style="margin:0 0 8px">Travel Plan Agent API 已启动</h2>
              <p>这里是<b>后端接口服务</b>。</p>
              <ul>
                <li>接口文档：<a href="/docs">/docs</a></li>
                <li>健康检查：<a href="/api/v1/health">/api/v1/health</a></li>
                <li>想在这里直接看到界面，先构建前端：
                  <code>cd travel-plan-web &amp;&amp; npm run build:agent</code></li>
                <li>开发模式前端：<a href="http://localhost:5173">http://localhost:5173</a></li>
              </ul>
            </body></html>
            """
        )
