import json

from langchain_core.tools import tool

from travel_plan_agent.config import get_settings


@tool(parse_docstring=True)
def get_guide(destination: str) -> str:
    """检索指定城市的旅游攻略素材，用于规划旅行路线。

    会调用网络搜索获取该城市排名靠前的公开攻略笔记，
    返回前 5 条笔记的标题与正文，由你（agent）自行阅读并整合出最合适的行程计划。

    Args:
        destination: 目的地城市名称，例如"北京"、"成都"、"西安"

    Returns:
        该城市的攻略检索结果（前 5 条笔记的标题与正文），供你整合规划
    """
    key = get_settings().tavily_api_key
    if not key:
        return "未配置 Tavily API key，请在 .env 中设置 TAVILY_API_KEY"
    try:
        from langchain_tavily import TavilySearch

        search = TavilySearch(tavily_api_key=key, max_results=5)
        resp = search.invoke(
            {"query": f"{destination} 旅游攻略 经典路线 必去景点 几天行程"}
        )
        if isinstance(resp, str):
            resp = json.loads(resp)
        results = resp.get("results", []) if isinstance(resp, dict) else []
        if not results:
            return f"未找到「{destination}」的旅游攻略"
        lines = [
            f"【{destination}】旅游攻略检索（前 {len(results)} 条，请据此整合成行程计划）："
        ]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            content = (r.get("content") or "").strip()
            url = r.get("url", "")
            lines.append(f"\n--- 攻略 {i}：{title} ---\n{content}\n来源：{url}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取「{destination}」旅游攻略失败：{e}"
