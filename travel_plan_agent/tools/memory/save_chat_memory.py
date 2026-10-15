"""短期记忆工具（SQLite）：写入当前会话的对话内容。"""

from langchain.tools import ToolRuntime, tool

from travel_plan_agent.memory import get_short_memory
from travel_plan_agent.memory.runtime import resolve_thread_id, resolve_user_id


@tool(parse_docstring=True)
def save_chat_memory(
    content: str,
    runtime: ToolRuntime,
) -> str:
    """把当前会话中的关键信息写入短期记忆（SQLite，按 thread_id 隔离）。

    短期记忆保存「本次对话的上下文」，用于后续轮次延续同一份行程方案。
    总结格式示范：用户需求、已确定的日期/预算/人数、已敲定的每日路线等。

    Args:
        content: 需要记住的内容，用一句话说清楚（例如"用户共2人，预算5000元，5月1日出发"）
        runtime: 工具运行时（自动提供 thread_id）
    """
    text = (content or "").strip()
    if not text:
        return "内容为空，未保存"
    thread_id = resolve_thread_id(runtime)
    user_id = resolve_user_id(runtime)
    memory = get_short_memory()
    # 去重：模型可能把同一条信息反复总结进来，最近 10 条里出现过就跳过
    recent = memory.get(thread_id=thread_id, limit=10)
    if any(r.content.strip() == text for r in recent):
        return "该信息已在短期记忆中，跳过重复保存"
    memory.save(
        text,
        thread_id=thread_id,
        user_id=user_id,
        role="assistant",
        metadata={"kind": "dialog"},
    )
    total = memory.count(thread_id=thread_id)
    return f"已保存到短期记忆（会话 {thread_id}，当前共 {total} 条）"
