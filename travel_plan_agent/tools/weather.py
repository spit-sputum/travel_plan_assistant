import httpx
from langchain_core.tools import tool

from travel_plan_agent.config import get_settings


@tool(parse_docstring=True)
def get_weather(city: str, days: int = 3) -> str:
    """获取目的地城市未来几天的天气预报。

    Args:
        city: 城市名称
        days: 预报天数，支持 3/7/10/15/30，默认 3
    """
    settings = get_settings()
    if not settings.hefeng_key:
        return "未配置和风天气 API key，请在 .env 中设置 HEFENG_KEY"
    host = settings.hefeng_host.rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "https://" + host
    headers = {"X-QW-Api-Key": settings.hefeng_key}
    days_map = {3: "3d", 7: "7d", 10: "10d", 15: "15d", 30: "30d"}
    d = days_map.get(days, "3d")
    try:
        # 1.城市名匹配城市代码
        geo = httpx.get(
            f"{host}/geo/v2/city/lookup",
            params={"location": city},
            headers=headers,
            timeout=10,
        ).json()
        locations = geo.get("location", [])
        if not locations:
            return f"未找到城市：{city}"
        location_id = locations[0]["id"]

        # 2. 查询天气
        resp = httpx.get(
            f"{host}/v7/weather/{d}",
            params={"location": location_id},
            headers=headers,
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != "200":
            return f"天气查询失败：{data.get('code')}"
        daily = data.get("daily", [])
        if not daily:
            return f"未查询到 {city} 的天气"
        lines = [
            f"{item['fxDate']} {item['textDay']} "
            f"{item['tempMin']}~{item['tempMax']}℃ "
            f"{item['windDirDay']}{item['windScaleDay']}级"
            for item in daily
        ]
        return f"{city}未来{days}天预报：\n" + "\n".join(lines)
    except Exception as e:
        return f"天气查询失败：{e}"
