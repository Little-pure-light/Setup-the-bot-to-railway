"""
天氣查詢工具

使用 Open-Meteo（無需 API Key）：
1. Geocoding 解析地名
2. Forecast 取得目前天氣與簡短預報
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger("tools.weather")

# WMO weather interpretation codes (精簡)
_WMO = {
    0: "晴朗",
    1: "大致晴朗",
    2: "局部多雲",
    3: "多雲",
    45: "有霧",
    48: "霧凇",
    51: "細雨",
    53: "中雨絲",
    55: "大雨絲",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "陣雨",
    81: "中陣雨",
    82: "強陣雨",
    95: "雷雨",
    96: "雷雨夾冰雹",
    99: "強雷雨夾冰雹",
}


def _http_get_json(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "XiaochenguangBot/1.0 (weather-tool)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


async def _aget(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(None, lambda: _http_get_json(url, timeout)),
        timeout=timeout + 1,
    )


async def get_weather(
    location: str,
    days: int = 1,
) -> str:
    """
    查詢地點天氣。
    location: 城市或地區名稱（中英文皆可，如 台北、Tokyo）
    days: 預報天數 1-3
    """
    place = (location or "").strip()
    if not place:
        return "[WEATHER_ERROR] 請提供地點名稱，例如：台北、東京、Tokyo"
    if len(place) > 80:
        return "[WEATHER_ERROR] 地點名稱過長"

    try:
        n_days = max(1, min(3, int(days or 1)))
    except (TypeError, ValueError):
        n_days = 1

    try:
        geo_q = urllib.parse.urlencode(
            {
                "name": place,
                "count": 1,
                "language": "zh",
                "format": "json",
            }
        )
        geo = await _aget(f"https://geocoding-api.open-meteo.com/v1/search?{geo_q}")
        results = geo.get("results") or []
        if not results:
            return f"[WEATHER_EMPTY] 找不到地點「{place}」，請換個寫法試試"

        hit = results[0]
        lat = hit["latitude"]
        lon = hit["longitude"]
        name = hit.get("name") or place
        country = hit.get("country") or ""
        admin = hit.get("admin1") or ""
        label = "、".join(x for x in [name, admin, country] if x)

        forecast_q = urllib.parse.urlencode(
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": n_days,
            }
        )
        data = await _aget(f"https://api.open-meteo.com/v1/forecast?{forecast_q}")
        cur = data.get("current") or {}
        code = int(cur.get("weather_code") or 0)
        desc = _WMO.get(code, f"天氣代碼 {code}")
        temp = cur.get("temperature_2m")
        hum = cur.get("relative_humidity_2m")
        wind = cur.get("wind_speed_10m")
        unit_t = (data.get("current_units") or {}).get("temperature_2m", "°C")
        unit_w = (data.get("current_units") or {}).get("wind_speed_10m", "km/h")

        lines = [
            f"📍 {label}",
            f"目前：{desc}，氣溫 {temp}{unit_t}，濕度 {hum}%，風速 {wind}{unit_w}",
        ]

        daily = data.get("daily") or {}
        times = daily.get("time") or []
        if times:
            lines.append("預報：")
            for i, day in enumerate(times[:n_days]):
                dcode = int((daily.get("weather_code") or [0])[i] or 0)
                ddesc = _WMO.get(dcode, "")
                tmax = (daily.get("temperature_2m_max") or [None])[i]
                tmin = (daily.get("temperature_2m_min") or [None])[i]
                pop = (daily.get("precipitation_probability_max") or [None])[i]
                lines.append(
                    f"  · {day}：{ddesc}，{tmin}~{tmax}{unit_t}"
                    + (f"，降雨機率 {pop}%" if pop is not None else "")
                )

        logger.info(f"✅ weather {place} -> {label}")
        return "\n".join(lines)
    except asyncio.TimeoutError:
        return "[WEATHER_TIMEOUT] 天氣查詢逾時，請稍後再試"
    except Exception as e:
        logger.warning(f"⚠️ weather error: {e}")
        return f"[WEATHER_ERROR] 天氣查詢失敗（{type(e).__name__}）"
