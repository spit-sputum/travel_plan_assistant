"""长期记忆工具（Chroma）：语义检索长期记忆。"""

from langchain.tools import ToolRuntime, tool

from travel_plan_agent.memory import get_long_memory
from travel_plan_agent.memory.runtime import resolve_thread_id, resolve_user_id


@tool(parse_docstring=True)
def get_longterm_memory(
    query: str,
    runtime: ToolRuntime,
    limit: int = 5,
) -> str:
    """按语义检索长期记忆（Chroma 向量库，跨会话有效）。

    在规划行程前调用，用传入的 query 去召回该用户的偏好与硬性约束，
    返回的内容需要在后续规划中严格遵守。

    Args:
        query: 检索用的自然语言描述，例如"用户的饮食禁忌与饮食偏好"
        limit: 返回条数，默认 5
        runtime: 工具运行时（自动提供 thread_id 与 user_id）
    """
    query = (query or "").strip()
    if not query:
        return "query 不能为空，请描述你想回忆的用户信息"
    user_id = resolve_user_id(runtime)
    thread_id = resolve_thread_id(runtime)
    records = get_long_memory().get(
        thread_id=thread_id,
        user_id=user_id,
        query=query,
        limit=max(1, int(limit)),
        scope="user",
    )
    if not records:
        return f"长期记忆中暂无与「{query}」相关的内容"
    lines = [f"长期记忆检索（用户 {user_id}，命中 {len(records)} 条）："]
    for i, r in enumerate(records, 1):
        score = f"，相似度 {r.score}" if r.score is not None else ""
        kind = r.metadata.get("kind", "fact")
        lines.append(f"{i}. [{kind}]{score} {r.content}")
    return "\n".join(lines)