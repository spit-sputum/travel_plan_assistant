import json
import re

from langchain_core.tools import tool

from travel_plan_agent.config import get_settings


def _extract(content: str, patterns):
    """按多个正则依次尝试从文本里提取第一个命中项"""
    for p in patterns:
        m = re.search(p, content)
        if m:
            return m.group(1).strip()
    return None


@tool(parse_docstring=True)
def get_restaurant(location: str) -> str:
    """查询某位置周边的推荐餐厅，用于为旅行路线沿途补充餐饮建议。

    会在小红书等公开笔记中检索该位置附近的人气餐厅，并给出地址与人均价格参考，
    列出周边评分靠前的餐厅。

    Args:
        location: 周边位置，例如"天安门附近"、"西湖边"、"故宫周边"

    Returns:
        周边推荐餐厅（名称、地址、人均价格、来源），按相关度取前五
    """
    key = get_settings().tavily_api_key
    if not key:
        return "未配置 Tavily API key，请在 .env 中设置 TAVILY_API_KEY"

    try:
        from langchain_tavily import TavilySearch

        search = TavilySearch(tavily_api_key=key, max_results=8)
        resp = search.invoke(
            {
                "query": f"{location} 美食 餐厅 推荐 人均 地址",
                "include_domains": ["xiaohongshu.com"],
            }
        )
        if isinstance(resp, str):
            resp = json.loads(resp)
        results = resp.get("results", []) if isinstance(resp, dict) else []
        if not results:
            return f"未找到「{location}」周边餐厅信息"

        # 按搜索相关度（score）降序取前五
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        top = results[:5]

        lines = [f"【{location}】周边推荐餐厅 Top5："]
        for i, r in enumerate(top, 1):
            title = r.get("title", "")
            content = r.get("content") or ""
            url = r.get("url", "")
            price = _extract(
                content,
                [
                    r"人均[约]?\s*(\d+)\s*元",
                    r"¥\s*(\d+)",
                    r"(\d+)\s*元/人",
                    r"人均\s*(\d+)",
                ],
            )
            addr = _extract(content, [r"地址[：:]\s*([^\n，。]+)", r"位于([^\n，。]+)"])
            lines.append(
                f"{i}. {title}\n"
                f"   地址：{addr or '详见来源链接'}\n"
                f"   人均：{('约 ' + price + ' 元') if price else '详见来源链接'}\n"
                f"   来源：{url}"
            )
        lines.append("（注：评分与价格以平台实际为准，此处按搜索相关度排序推荐）")
        return "\n".join(lines)
    except Exception as e:
        return f"获取「{location}」周边餐厅失败：{e}"
