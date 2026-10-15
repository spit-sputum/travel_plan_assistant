import httpx
from langchain_core.tools import tool

from travel_plan_agent.config import get_settings


@tool(parse_docstring=True)
def get_traffic(origin: str, destination: str, mode: str = "transit") -> str:
    """查询两个地点之间的交通路线规划，用于规划目的地内部的出行方式，默认出行方式为驾车。

    Args:
        origin: 出发地名称，例如"北京西站"、"天安门"
        destination: 目的地名称，例如"首都国际机场"、"故宫"
        mode: 出行方式，可选值：
            transit   - 公交/地铁
            driving   - 驾车（默认，适合市内出行）
            walking   - 步行

    Returns:
        路线规划的文字描述（距离、预计耗时、换乘/路线概述）
    """
    key = get_settings().gaode_key
    if not key:
        return "未配置高德地图 API key，请在 .env 中设置 GAODE_KEY"

    def geocode(name: str):
        """地名 -> (经度,纬度, 城市名)，高德路线规划只接收坐标"""
        try:
            r = httpx.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"address": name, "key": key},
                timeout=10,
            )
            d = r.json()
            if d.get("status") == "1" and d.get("geocodes"):
                geo = d["geocodes"][0]
                return geo["location"], geo.get("city", "")
            return None, ""
        except Exception:
            return None, ""

    try:
        o_loc, o_city = geocode(origin)
        d_loc, _ = geocode(destination)  # 获取出发点和目的地的坐标，顺带城市名
        if not o_loc or not d_loc:
            miss = []
            if not o_loc:
                miss.append("出发地")
            if not d_loc:
                miss.append("目的地")
            return f"无法识别{'、'.join(miss)}，请提供更具体的地点名称"

        mode_cfg = {
            "transit": ("v3/direction/transit/integrated", "公交/地铁"),
            "driving": ("v3/direction/driving", "驾车"),
            "walking": ("v3/direction/walking", "步行"),
        }
        if mode not in mode_cfg:
            mode = "driving"  # 默认为开车
        api_path, label = mode_cfg[mode]

        params = {
            "key": key,
            "origin": o_loc,
            "destination": d_loc,
            "extensions": "base",
        }
        if mode == "transit":
            params["city"] = o_city or origin  # 公交规划需要起点城市

        r = httpx.get(f"https://restapi.amap.com/{api_path}", params=params, timeout=10)
        d = r.json()
        if d.get("status") != "1":
            return f"路线规划失败：{d.get('info', '未知错误')}"

        route = d.get("route", {})

        if mode == "transit":
            distance = int(route.get("distance", 0))
            dist_text = (
                f"{distance / 1000:.1f} 公里" if distance >= 1000 else f"{distance} 米"
            )
            lines = [f"{origin} → {destination}（{label}）", f"全程约 {dist_text}"]
            transits = route.get("transits", [])
            if transits:
                t = transits[0]
                minutes = int(t.get("duration", 0)) // 60
                lines.append(f"预计耗时约 {minutes} 分钟")
                if t.get("cost"):
                    lines.append(f"票价约 {t['cost']} 元")
                bus_names = []
                for seg in t.get("segments", []):
                    for bl in seg.get("bus", {}).get("buslines", []):
                        if bl.get("name"):
                            bus_names.append(bl["name"])
                if bus_names:
                    lines.append("参考路线：" + " → ".join(bus_names[:4]))
        else:  # driving / walking：距离与时长都在 route.paths[0] 中（route 顶层没有）
            paths = route.get("paths", [])
            if paths:
                p = paths[0]
                distance = int(p.get("distance", 0))
                duration = int(p.get("duration", 0))
            else:
                distance = duration = 0
            dist_text = (
                f"{distance / 1000:.1f} 公里" if distance >= 1000 else f"{distance} 米"
            )
            minutes = duration // 60
            lines = [
                f"{origin} → {destination}（{label}）",
                f"全程约 {dist_text}",
                f"预计耗时约 {minutes} 分钟",
            ]

        return "\n".join(lines)
    except Exception as e:
        return f"路线规划失败：{e}"
