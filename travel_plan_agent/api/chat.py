"""对话与会话管理路由。

端点（前缀 /api/v1/chat）：
- POST   /message            一次性返回完整回复（非流式）
- POST   /stream             SSE 流式：start → tool_call/tool_result → token → done
- GET    /sessions           会话列表
- GET    /history            某会话的历史消息
- DELETE /session/{id}       删除会话（短期记忆 + 检查点）
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import APIRouter, Query
from langchain_core.messages import RemoveMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from sse_starlette.sse import EventSourceResponse

from travel_plan_agent.api.deps import require_agent
from travel_plan_agent.api.schemas import (
    ApiResponse,
    ChatData,
    ChatRequest,
    SessionInfo,
    ToolCallInfo,
    ToolResultInfo,
)
from travel_plan_agent.build_agent import get_checkpointer
from travel_plan_agent.memory import get_short_memory

router = APIRouter(prefix="/chat", tags=["chat"])

PREVIEW_LEN = 80  # 会话列表预览长度
RESULT_PREVIEW_LEN = 240  # 工具结果摘要长度
_END = object()  # 同步事件流迭代结束的哨兵


# ------------------------------------------------------------------ 工具函数
INTERRUPTED_TOOL_RESULT = (
    "（上一轮该工具调用被中断，没有执行完成。请忽略这次调用，"
    "如仍需要这些信息请重新调用工具。）"
)


def new_conversation_id() -> str:
    """生成会话 ID：前端首轮不传 conversationId 时由后端生成。"""
    return f"thread_{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}"


def _sanitize_tool_call_sequence(messages: list[Any]) -> list[Any]:
    """让每条带 tool_calls 的 AI 消息后面紧跟它全部的工具响应。

    用户中断（点「停止生成」/ 关闭页面）会让 checkpoint 停在半个步骤上：
    模型已经声明要调用工具，工具响应却没能写回。这样的历史再发给大模型，
    服务端会直接报 400：
    "An assistant message with 'tool_calls' must be followed by tool messages
     responding to each 'tool_call_id'"。
    这里把缺失的响应补成一条明确的「已中断」工具消息，让序列重新合法。
    """
    sanitized: list[Any] = []
    index = 0
    total = len(messages)
    while index < total:
        message = messages[index]
        sanitized.append(message)
        index += 1
        calls = list(getattr(message, "tool_calls", None) or [])
        if not calls:
            continue
        wanted = [str(call.get("id") or "") for call in calls]
        answers: dict[str, Any] = {}
        # 收集紧随其后、确实属于本次调用的工具响应
        while index < total and getattr(messages[index], "type", "") == "tool":
            tool_call_id = str(getattr(messages[index], "tool_call_id", "") or "")
            if tool_call_id not in wanted or tool_call_id in answers:
                break
            answers[tool_call_id] = messages[index]
            index += 1
        for call in calls:
            call_id = str(call.get("id") or "")
            if call_id in answers:
                sanitized.append(answers[call_id])
            else:
                sanitized.append(
                    ToolMessage(
                        content=INTERRUPTED_TOOL_RESULT,
                        tool_call_id=call_id,
                        name=str(call.get("name") or ""),
                        status="error",
                    )
                )
    return sanitized


def repair_dangling_tool_calls(
    agent: Any, conversation_id: str, saver: Any = None
) -> int:
    """修复被中断的会话：补齐「悬空」的工具调用响应。

    返回补齐的条数，0 表示无需修复或修复失败（修复失败不应影响正常对话）。
    """
    try:
        saver = saver if saver is not None else get_checkpointer()
        config = {"configurable": {"thread_id": conversation_id}}
        # 读「已提交」的消息（不能走 get_state：它会把未提交的 pending writes 也算进来）
        snapshot = saver.get_tuple(config)
        if snapshot is None:
            return 0
        messages = list(
            snapshot.checkpoint.get("channel_values", {}).get("messages") or []
        )
        if not messages:
            return 0
        sanitized = _sanitize_tool_call_sequence(messages)
        if sanitized == messages:
            return 0
        agent.update_state(
            config,
            {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *sanitized]},
            as_node="tools",  # 当作工具节点的产出写入，图的下一步仍是模型节点
        )
        return len(sanitized) - len(messages)
    except Exception:  # noqa: BLE001 - 修复只是兜底，失败不应打断对话
        return 0


def _to_text(content: Any) -> str:
    """把消息内容（str 或分段列表）压平成纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content or "")


def _chunk_text(chunk: Any) -> str:
    """从流式 chunk 中取文本；工具调用块的 content 通常为空，会被自然跳过。"""
    if chunk is None:
        return ""
    return _to_text(getattr(chunk, "content", ""))


def _current_turn_messages(messages: list[Any]) -> list[Any]:
    """只取本轮产生的消息（最后一条 user 消息之后的部分），避免历史工具调用重复展示。"""
    last_user = -1
    for i, m in enumerate(messages):
        if getattr(m, "type", "") == "human":
            last_user = i
    return messages[last_user + 1 :] if last_user >= 0 else messages


def _last_ai_text(messages: list[Any]) -> str:
    """取最后一条 AI 消息的文本。"""
    for m in reversed(messages):
        if getattr(m, "type", "") == "ai":
            return _to_text(getattr(m, "content", ""))
    return ""


def _extract_tool_meta(
    messages: list[Any],
) -> tuple[list[ToolCallInfo], list[ToolResultInfo]]:
    """从消息序列中提取工具调用与工具返回，供前端展示。"""
    tool_calls: list[ToolCallInfo] = []
    tool_results: list[ToolResultInfo] = []
    for m in messages:
        kind = getattr(m, "type", "")
        if kind == "ai":
            for call in getattr(m, "tool_calls", None) or []:
                tool_calls.append(
                    ToolCallInfo(
                        name=str(call.get("name", "")),
                        args=call.get("args") or {},
                        status="done",
                    )
                )
        elif kind == "tool":
            tool_results.append(
                ToolResultInfo(
                    name=str(getattr(m, "name", "") or ""),
                    preview=_to_text(getattr(m, "content", ""))[:RESULT_PREVIEW_LEN],
                )
            )
    return tool_calls, tool_results


def _run_agent(message: str, conversation_id: str, user_id: str) -> list[Any]:
    """同步执行一轮对话，返回全部消息。"""
    agent = require_agent()
    # 上一轮被中断可能留下残缺的工具调用记录，先补齐再继续对话
    repair_dangling_tool_calls(agent, conversation_id)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": conversation_id, "user_id": user_id}},
    )
    return list(result.get("messages", []))


def _persist_turn(
    conversation_id: str,
    user_id: str,
    user_message: str,
    assistant_text: str,
    interrupted: bool = False,
) -> None:
    """把本轮问答写入短期记忆，保证会话列表 / 历史有数据。

    记忆模块原本只由 Agent 主动调用工具写入（总结形式），
    这里额外落一份原始问答，两者共存、互不冲突。

    中断（用户点了"停止生成"）时的处理：
    - 已经输出了半截内容 → 原样保留，并打上 interrupted 标记
    - 完全没有内容 → 补一条占位说明，避免留下"只有提问没有回答"的孤儿消息
    """
    memory = get_short_memory()
    assistant_meta: dict[str, Any] = {"kind": "dialog", "source": "api"}
    if interrupted:
        assistant_meta["interrupted"] = True
    try:
        memory.save(
            user_message,
            thread_id=conversation_id,
            user_id=user_id,
            role="user",
            metadata={"kind": "dialog", "source": "api"},
        )
        text = (assistant_text or "").strip()
        if not text and interrupted:
            text = "（用户已中断本次生成）"
        if text:
            memory.save(
                text,
                thread_id=conversation_id,
                user_id=user_id,
                role="assistant",
                metadata=assistant_meta,
            )
    except Exception:  # noqa: BLE001 - 落库失败不影响对话返回
        pass


# ------------------------------------------------------------------ 对话接口
@router.post("/message")
def chat_message(req: ChatRequest) -> dict[str, Any]:
    """非流式对话：等 Agent 全部跑完再一次性返回。

    注意用 `def` 而非 `async def`，FastAPI 会自动放到线程池，不阻塞事件循环。
    """
    message = (req.message or "").strip()
    if not message:
        return ApiResponse(code=400, success=False, message="message 不能为空").model_dump()

    conversation_id = (req.conversation_id or "").strip() or new_conversation_id()
    user_id = (req.user_id or "").strip() or "default_user"

    started = time.time()
    try:
        messages = _run_agent(message, conversation_id, user_id)
    except Exception as exc:  # noqa: BLE001 - 配置缺失 / 初始化失败时返回中文提示
        return ApiResponse(code=503, success=False, message=str(exc)).model_dump()
    turn = _current_turn_messages(messages)
    tool_calls, tool_results = _extract_tool_meta(turn)

    content = _last_ai_text(turn)
    _persist_turn(conversation_id, user_id, message, content)

    data = ChatData(
        conversationId=conversation_id,
        messageId=uuid.uuid4().hex,
        content=content,
        toolCalls=tool_calls,
        toolResults=tool_results,
        elapsed=round(time.time() - started, 2),
    )
    return ApiResponse(data=data.model_dump()).model_dump()


@router.post("/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    """SSE 流式对话：边生成边推送，前端可显示打字机效果与工具调用进度。"""
    message = (req.message or "").strip()
    conversation_id = (req.conversation_id or "").strip() or new_conversation_id()
    user_id = (req.user_id or "").strip() or "default_user"
    message_id = uuid.uuid4().hex

    def sse(event: str, payload: dict[str, Any]) -> dict[str, str]:
        return {"event": event, "data": json.dumps(payload, ensure_ascii=False, default=str)}

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        answer_parts: list[str] = []  # 累积本轮回答，结束时写入短期记忆
        yield sse("start", {"conversationId": conversation_id, "messageId": message_id})
        if not message:
            yield sse("error", {"error": "message 不能为空"})
            yield sse("done", {"conversationId": conversation_id, "messageId": message_id})
            return
        try:
            agent = require_agent()
        except Exception as exc:  # noqa: BLE001 - 配置缺失时通过事件告知前端
            yield sse("error", {"error": str(exc)})
            yield sse("done", {"conversationId": conversation_id, "messageId": message_id})
            return
        # 上一轮被中断可能留下残缺的工具调用记录，先补齐再继续对话
        await asyncio.to_thread(repair_dangling_tool_calls, agent, conversation_id)
        # 说明：checkpointer 用的是同步 SqliteSaver，不支持异步接口，
        # 所以这里用同步的 stream()，并在事件循环外的线程里逐条拉取。
        # stream_mode：
        #   messages → LLM 逐 token 输出（打字机效果）
        #   updates  → 每个节点的完整产出（从中提取工具调用与工具返回）
        iterator = iter(
            agent.stream(
                {"messages": [{"role": "user", "content": message}]},
                config={
                    "configurable": {"thread_id": conversation_id, "user_id": user_id}
                },
                stream_mode=["messages", "updates"],
            )
        )
        seen_tools: set[str] = set()
        interrupted = False  # 用户中途点了"停止生成"或断开连接
        pull_state = {"abandoned": False}

        def pull() -> Any:
            """在工作线程里拉取下一个事件，并在需要时由本线程关闭生成器。

            请求被取消时，工作线程可能仍在执行生成器，此时从事件循环里调用
            iterator.close() 会抛 "generator already executing" 并被吞掉：
            生成器被遗弃、图继续在后台跑完，checkpoint 就停在了
            「模型声明了工具调用、却没有工具响应」的半截状态。
            让持有生成器的线程自己收尾，才不会留下这种残缺历史。
            """
            try:
                return next(iterator, _END)
            finally:
                if pull_state["abandoned"]:
                    try:
                        iterator.close()
                    except Exception:  # noqa: BLE001 - 可能已被关闭
                        pass

        try:
            while True:
                item = await asyncio.to_thread(pull)
                if item is _END:
                    break
                mode, chunk = item
                if mode == "messages":
                    msg_chunk, _meta = chunk
                    # 只转发模型生成的文本分片，忽略工具消息分片
                    if "AI" not in type(msg_chunk).__name__:
                        continue
                    text = _chunk_text(msg_chunk)
                    if text:
                        answer_parts.append(text)
                        yield sse("token", {"content": text})
                elif mode == "updates":
                    for node_update in chunk.values():
                        if not isinstance(node_update, dict):
                            continue
                        for msg in node_update.get("messages") or []:
                            msg_type = getattr(msg, "type", "")
                            if msg_type == "ai":
                                for call in getattr(msg, "tool_calls", None) or []:
                                    key = f"{call.get('name')}|{call.get('args')}"
                                    if key in seen_tools:  # 去重，避免重复推送
                                        continue
                                    seen_tools.add(key)
                                    yield sse(
                                        "tool_call",
                                        {
                                            "name": call.get("name", ""),
                                            "args": call.get("args") or {},
                                        },
                                    )
                            elif msg_type == "tool":
                                yield sse(
                                    "tool_result",
                                    {
                                        "name": getattr(msg, "name", "") or "",
                                        "preview": _to_text(
                                            getattr(msg, "content", "")
                                        )[:RESULT_PREVIEW_LEN],
                                    },
                                )
        except asyncio.CancelledError:
            # 前端点了"停止生成"或关闭页面，Starlette 会取消本生成器。
            # 标记后继续抛出，让取消语义正常传播。
            interrupted = True
            pull_state["abandoned"] = True
            raise
        except GeneratorExit:
            # 生成器被关闭（连接已断开）
            interrupted = True
            pull_state["abandoned"] = True
            raise
        except Exception as exc:  # noqa: BLE001 - 异常也通过事件告知前端
            yield sse("error", {"error": f"{type(exc).__name__}: {exc}"})
        finally:
            # 通知后台生成器收尾：若工作线程仍在拉取，由它自己关闭（见 pull()）；
            # 否则在这里关闭。失败也无妨，只是生成器会被遗弃。
            pull_state["abandoned"] = True
            try:
                iterator.close()
            except Exception:  # noqa: BLE001
                pass
            # 直接同步写入（毫秒级）：即使前端提前断开连接，
            # finally 里的同步代码仍会执行完，避免这一轮对话丢失。
            # interrupted=True 时记忆里会打标记，并在无内容时补占位说明。
            _persist_turn(
                conversation_id,
                user_id,
                message,
                "".join(answer_parts),
                interrupted,
            )
            # 连接已断开时不能再写事件，否则会抛异常
            if not interrupted:
                yield sse(
                    "done",
                    {"conversationId": conversation_id, "messageId": message_id},
                )

    return EventSourceResponse(event_generator(), ping=15000)


# ------------------------------------------------------------------ 会话接口
@router.get("/sessions")
def list_sessions(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    """会话列表：按最后活跃时间倒序。"""
    memory = get_short_memory()
    sessions: list[SessionInfo] = []
    for thread_id in memory.list_threads():
        records = memory.get(thread_id=thread_id, limit=1)
        last = records[-1] if records else None
        sessions.append(
            SessionInfo(
                conversationId=thread_id,
                count=memory.count(thread_id=thread_id),
                lastActive=last.created_at if last else "",
                preview=last.content[:PREVIEW_LEN] if last else "",
            )
        )
    sessions.sort(key=lambda s: s.lastActive, reverse=True)
    return ApiResponse(data=[s.model_dump() for s in sessions[:limit]]).model_dump()


@router.get("/history")
def chat_history(
    conversationId: str = Query(..., description="会话 ID"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    """读取某会话的历史消息（按时间正序）。"""
    records = get_short_memory().get(thread_id=conversationId, limit=limit)
    messages = [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "createdAt": r.created_at,
            "metadata": r.metadata,
        }
        for r in records
    ]
    return ApiResponse(
        data={"conversationId": conversationId, "messages": messages}
    ).model_dump()


@router.delete("/session/{conversation_id}")
def delete_session(conversation_id: str) -> dict[str, Any]:
    """删除会话：同时清空短期记忆与该会话的对话检查点。"""
    removed = get_short_memory().clear(thread_id=conversation_id)
    checkpoint_cleared = False
    try:
        get_checkpointer().delete_thread(conversation_id)
        checkpoint_cleared = True
    except Exception:  # noqa: BLE001 - 检查点清理失败不影响记忆清理结果
        pass
    return ApiResponse(
        data={
            "conversationId": conversation_id,
            "removed": removed,
            "checkpointCleared": checkpoint_cleared,
        }
    ).model_dump()
