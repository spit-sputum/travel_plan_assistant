"""HTTP 接口的请求 / 响应模型（前端契约）。

约定：
- 所有接口统一返回信封 `{code, success, message, data}`，前端只读 `data`。
- 字段名采用前端友好的驼峰（conversationId / userId / toolCalls ...）。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiResponse(BaseModel):
    """统一响应信封。成功 code=0/success=true，失败 code!=0/success=false。"""

    code: int = 0
    success: bool = True
    message: str = "ok"
    data: Any = None


class ChatRequest(BaseModel):
    """对话请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., description="用户输入内容")
    conversation_id: str | None = Field(
        default=None, alias="conversationId", description="会话 ID；首轮不传，由后端生成"
    )
    user_id: str = Field(
        default="default_user", alias="userId", description="用户 ID（长期记忆的隔离键）"
    )


class ToolCallInfo(BaseModel):
    """一次工具调用（用于前端展示"正在查攻略 / 正在算路线"）。"""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: str = "done"


class ToolResultInfo(BaseModel):
    """一次工具返回（preview 为截断后的结果摘要）。"""

    name: str
    preview: str = ""


class ChatData(BaseModel):
    """对话响应数据。"""

    conversationId: str
    messageId: str
    content: str
    toolCalls: list[ToolCallInfo] = Field(default_factory=list)
    toolResults: list[ToolResultInfo] = Field(default_factory=list)
    elapsed: float = 0.0


class SessionInfo(BaseModel):
    """会话列表项。"""

    conversationId: str
    count: int = 0
    lastActive: str = ""
    preview: str = ""
