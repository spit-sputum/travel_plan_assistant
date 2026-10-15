import json
import re
from datetime import datetime

from langchain_core.tools import tool

from travel_plan_agent.config import get_settings


def _extract(text, patterns):
    """按多个正则依次尝试从文本里提取第一个命中项"""
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return None


@tool(parse_docstring=True)
def get_hotel(origin: str, target: str, date: datetime) -> str:
    """查询目的地旅游路线附近的酒店，列出若干候选供 agent 选择住宿。

    直接在互联网上搜索目的地（或沿线）附近的酒店，提取评分、评语与价格，
    返回 3 个候选交由 agent 结合行程路线挑选。

    Args:
        origin: 出发地（仅用于上下文）
        target: 目的地城市/区域，例如"北京"、"东京"、"西湖"
        date: 入住日期（datetime）

    Returns:
        目的地附近推荐酒店（名称、评分、评语、价格、来源），列出 3 个供选择
    """
    key = get_settings().tavily_api_key
    if not key:
        return "未配置 Tavily API key，请在 .env 中设置 TAVILY_API_KEY"

    date_str = ""
    if date:
        try:
            date_str = date.strftime("%Y-%m-%d")
        except Exception:
            date_str = str(date)

    try:
        from langchain_tavily import TavilySearch

        search = TavilySearch(tavily_api_key=key, max_results=6)
        route = f"{origin}→{target}" if origin and origin != target else target
        query = f"{route} {date_str} 附近 酒店 推荐 评分 价格 点评".strip()
        resp = search.invoke({"query": query})
        if isinstance(resp, str):
            resp = json.loads(resp)
        results = resp.get("results", []) if isinstance(resp, dict) else []

        if not results:
            return f"未找到「{target}」附近的酒店信息"

        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        top = results[:3]

        lines = [f"【{target} 附近推荐酒店】（列出 3 个供选择）："]
        for i, r in enumerate(top, 1):
            title = r.get("title", "")
            content = r.get("content") or ""
            url = r.get("url", "")
            text = f"{title} {content}"
            score = _extract(
                text,
                [
                    r"评分[：:]?\s*([\d.]+)",
                    r"([\d.]+)\s*分",
                    r"([\d.]+)\s*(?:/10|好|不错|优)",
                ],
            )
            price = _extract(
                text,
                [
                    r"¥\s*([\d,]+)",
                    r"\$\s*([\d,]+)",
                    r"(\d+)\s*元/晚",
                    r"(\d+)\s*起",
                    r"起\s*([\d,]+)",
                    r"RM\s*([\d,]+)",
                    r"([\d,]+)\s*(?:元|美元|美金|RMB|CNY)",
                ],
            )
            comment = content.strip().replace("\n", " ")
            if len(comment) > 60:
                comment = comment[:60] + "…"
            lines.append(
                f"{i}. {title}\n"
                f"   评分：{score or '详见来源'}\n"
                f"   价格：{('¥' + price) if price else '详见来源'}\n"
                f"   评语：{comment or '详见来源'}\n"
                f"   来源：{url}"
            )
        lines.append("（注：评分/价格以平台实际为准，请结合实际路线挑选）")
        return "\n".join(lines)
    except Exception as e:
        return f"获取「{target}」附近酒店失败：{e}"
