import json

from langchain_core.tools import tool

from travel_plan_agent.config import get_settings

# 基础货币别名归一化（仅用于判断是否同种货币）
_CURRENCY_ALIAS = {
    "人民币": "CNY",
    "rmb": "CNY",
    "cny": "CNY",
    "元": "CNY",
    "美元": "USD",
    "美金": "USD",
    "usd": "USD",
    "$": "USD",
    "日元": "JPY",
    "jpy": "JPY",
    "欧元": "EUR",
    "eur": "EUR",
    "€": "EUR",
    "港币": "HKD",
    "hkd": "HKD",
    "英镑": "GBP",
    "gbp": "GBP",
    "£": "GBP",
    "韩元": "KRW",
    "krw": "KRW",
    "泰铢": "THB",
    "thb": "THB",
}


def _norm(code: str) -> str:
    """把中文货币名/符号/小写代码统一成 ISO 三字大写代码，便于判断同种货币"""
    s = (code or "").strip()
    if len(s) == 3 and s.isalpha():
        return s.upper()
    return _CURRENCY_ALIAS.get(s.lower(), s.upper())


@tool(parse_docstring=True)
def currency_exchange(origin: str, target: str, amount: float) -> str:
    """在目的地与出发地不是同一国家/地区时，检索两地货币的实时汇率资料，供行程预算参考。

    通过网上搜索获取实时汇率的原始检索内容（标题、摘要、来源链接），交由 agent 自行提取
    汇率并完成换算；若两地货币相同（如均为人民币）则直接说明无需换算。

    Args:
        origin: 原货币，支持中文（如"人民币"、"美元"）或 ISO 代码（如"CNY"、"USD"）
        target: 目标货币，同上
        amount: 需要兑换的金额（供 agent 参考，由 agent 完成实际换算）

    Returns:
        实时汇率的网络检索原始内容（标题、摘要、来源），或"无需换算"提示
    """
    o = _norm(origin)
    t = _norm(target)
    if o == t:
        return f"{origin} 与 {target} 货币相同（{o}），无需换算，金额仍为 {amount} {o}"

    key = get_settings().tavily_api_key
    if not key:
        return "未配置 Tavily API key，请在 .env 中设置 TAVILY_API_KEY"

    try:
        from langchain_tavily import TavilySearch

        search = TavilySearch(tavily_api_key=key, max_results=3)
        resp = search.invoke({"query": f"{origin} 兑 {target} 实时汇率 今日"})
        if isinstance(resp, str):
            resp = json.loads(resp)
        results = resp.get("results", []) if isinstance(resp, dict) else []
        if not results:
            return f"未检索到「{origin}→{target}」的实时汇率资料"

        lines = [
            f"【{origin} → {target} 实时汇率检索结果】（请据此自行换算 {amount} {o}）："
        ]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            content = (r.get("content") or "").strip()
            url = r.get("url", "")
            lines.append(f"{i}. {title}\n   {content}\n   来源：{url}")
        return "\n".join(lines)
    except Exception as e:
        return f"查询「{origin}→{target}」汇率失败：{e}"
