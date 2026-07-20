"""取得目前時間工具"""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Optional
import logging

logger = logging.getLogger("tools.time")

# 常見時區偏移（Windows 無 tzdata 時的備援）
_FIXED_OFFSETS = {
    "UTC": 0,
    "Asia/Taipei": 8,
    "Asia/Tokyo": 9,
    "Asia/Shanghai": 8,
    "Asia/Hong_Kong": 8,
    "America/New_York": -5,
    "America/Los_Angeles": -8,
    "Europe/London": 0,
}


async def get_current_time(timezone: Optional[str] = None) -> str:
    """
    回傳目前時間字串。
    timezone: IANA 名稱，預設 Asia/Taipei；失敗則用固定偏移或 UTC。
    """
    tz_name = (timezone or "Asia/Taipei").strip() or "Asia/Taipei"
    try:
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
            weekday = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
            return (
                f"目前時間（{tz_name}）：{now.strftime('%Y-%m-%d %H:%M:%S')}，"
                f"星期{weekday}，UTC 偏移 {now.strftime('%z')}"
            )
        except Exception:
            # Windows 可能缺 tzdata；用固定偏移備援
            hours = _FIXED_OFFSETS.get(tz_name)
            if hours is None:
                # 嘗試解析 UTC+8 / GMT+8
                import re

                m = re.fullmatch(r"(?:UTC|GMT)([+-]\d{1,2})", tz_name, re.I)
                hours = int(m.group(1)) if m else 8 if "Taipei" in tz_name else 0
            offset = dt_timezone(timedelta(hours=hours))
            now = datetime.now(offset)
            weekday = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
            return (
                f"目前時間（{tz_name}，固定偏移 UTC{hours:+d}）："
                f"{now.strftime('%Y-%m-%d %H:%M:%S')}，星期{weekday}"
            )
    except Exception as e:
        logger.warning(f"⚠️ get_current_time 失敗: {e}")
        now = datetime.now(dt_timezone.utc)
        return f"目前時間（UTC fallback）：{now.isoformat()}"
