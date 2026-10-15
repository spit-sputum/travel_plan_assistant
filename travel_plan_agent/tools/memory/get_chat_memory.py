"""短期记忆工具（SQLite）：读取当前会话的对话内容。"""

from langchain.tools import ToolRuntime, tool

from travel_plan_agent.memory import get_short_memory
from travel_plan_agent.memory.runtime import resolve_thread_id, resolve_user_id


@tool(parse_docstring=True)
def get_chat_memory(
    runtime: ToolRuntime,
    limit: int = 10,
) -> str:
    """读取当前会话（thread_id）的短期记忆，按时间正序返回最近若干条内容。

    在继续修改行程、或用户提到"刚才/上次"时调用，避免重复询问已确认的信息。

    Args:
        limit: 返回条数，默认 10
        runtime: 工具运行时（自动提供 thread_id）
    """
    thread_id = resolve_thread_id(runtime)
    user_id = resolve_user_id(runtime)
    records = get_short_memory().get(
        thread_id=thread_id, user_id=user_id, limit=max(1, int(limit))
    )
    if not records:
        return f"会话 {thread_id} 的短期记忆中暂无内容"
    lines = [f"短期记忆（会话 {thread_id}，共 {len(records)} 条）："]
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. [{r.created_at}] {r.content}")
    return "\n".join(lines)