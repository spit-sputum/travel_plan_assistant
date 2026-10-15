import json

from langchain_core.tools import tool

from travel_plan_agent.config import get_settings


@tool(parse_docstring=True)
def get_attraction(spot: str) -> str:
    """查询某个景点的详细信息，用于补充确定路线中涉及景点的介绍、地址与游玩提示。

    通常在一个具体的旅行路线确定后调用，针对路线上的景点逐个获取资料。

    Args:
        spot: 景点名称，例如"故宫"、"天安门"、"西湖"

    Returns:
        该景点的攻略/介绍摘要（来自大众点评等公开笔记）
    """
    key = get_settings().tavily_api_key
    if not key:
        return "未配置 Tavily API key，请在 .env 中设置 TAVILY_API_KEY"

    try:
        from langchain_tavily import TavilySearch

        search = TavilySearch(tavily_api_key=key, max_results=5)
        resp = search.invoke(
            {
                "query": f"{spot} 景点 介绍 攻略 地址 游玩",
                "include_domains": ["dianping.com"],
            }
        )
        if isinstance(resp, str):
            resp = json.loads(resp)
        results = resp.get("results", []) if isinstance(resp, dict) else []
        if not results:
            return f"未找到「{spot}」的相关景点信息"

        lines = [f"【{spot}】景点信息（来源：大众点评等公开笔记）："]
        for i, r in enumerate(results[:5], 1):
            title = r.get("title", "")
            content = (r.get("content") or "").strip()
            url = r.get("url", "")
            lines.append(f"{i}. {title}\n   {content}\n   来源：{url}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取「{spot}」景点信息失败：{e}"
