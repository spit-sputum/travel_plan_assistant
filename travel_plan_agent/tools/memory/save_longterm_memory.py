"""长期记忆工具（Chroma）：写入跨会话的长期信息。"""

from langchain.tools import ToolRuntime, tool

from travel_plan_agent.memory import get_long_memory
from travel_plan_agent.memory.runtime import resolve_thread_id, resolve_user_id


@tool(parse_docstring=True)
def save_longterm_memory(
    content: str,
    runtime: ToolRuntime,
    kind: str = "fact",
) -> str:
    """把用户稳定的信息写入长期记忆（Chroma 向量库，跨会话有效）。

    长期记忆保存「以后每次都要记住」的偏好与约束，只写明确说过且长期成立的内容。
    适合记录：忌口与过敏、常住城市与预算区间、偏好的出行方式、对景点/酒店的标准等。

    Args:
        content: 需长期记住的完整表述，例如"用户对海鲜过敏，忌口任何贝类，不吃香菜等"
        kind: 类型，取值 preference（偏好）/ constraint（硬性约束）/ profile（用户画像）
        runtime: 工具运行时（自动提供 thread_id 与 user_id）
    """
    if not (content or "").strip():
        return "内容为空，未保存"
    kind = (kind or "fact").strip() or "fact"
    user_id = resolve_user_id(runtime)
    thread_id = resolve_thread_id(runtime)
    memory = get_long_memory()
    memory.save(
        content.strip(),
        thread_id=thread_id,
        user_id=user_id,
        role="assistant",
        metadata={"kind": kind},
    )
    total = memory.count(user_id=user_id)
    return f"已保存到长期记忆（用户 {user_id}，当前共 {total} 条）"
