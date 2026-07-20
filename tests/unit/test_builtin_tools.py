"""P1-05: 內建工具與 registry 安全行為"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.tools.calculator import calculate
from backend.tools.time_tool import get_current_time
from backend.tools.unit_convert import convert_units
from backend.tools.web_search import web_search, _sanitize_query, _clamp_max_results
from backend.tools.weather import get_weather
from backend.tools.reminder import manage_reminder
from backend.tools.registry import ToolRegistry, ToolSpec, BLOCKED_TOOL_NAMES


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_ok():
    assert "6" in await calculate("2*3")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_time_taipei():
    r = await get_current_time("Asia/Taipei")
    assert "目前時間" in r
    assert "202" in r  # year


@pytest.mark.unit
@pytest.mark.asyncio
async def test_convert_units_ok():
    r = await convert_units(1, "km", "m")
    assert "1000" in r


@pytest.mark.unit
def test_web_search_sanitize():
    assert _sanitize_query("") is None
    assert _sanitize_query("file://etc") is None
    assert _sanitize_query("  hello world  ") == "hello world"
    assert _clamp_max_results(99) == 5
    assert _clamp_max_results(0) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_web_search_invalid_query():
    r = await web_search("")
    assert "[SEARCH_INVALID]" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_web_search_mocked_success():
    with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key", "WEB_SEARCH_FALLBACK": "false"}, clear=False), patch(
        "backend.tools.web_search._search_tavily",
        new_callable=AsyncMock,
        return_value="📋 摘要：Python is a language",
    ):
        r = await web_search("python")
        assert "Python" in r or "摘要" in r

@pytest.mark.unit
@pytest.mark.asyncio
async def test_weather_empty_location():
    r = await get_weather("")
    assert "[WEATHER_ERROR]" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_weather_mocked():
    fake_geo = {
        "results": [{"name": "Taipei", "latitude": 25.0, "longitude": 121.5, "country": "TW"}]
    }
    fake_forecast = {
        "current": {
            "temperature_2m": 28,
            "weather_code": 0,
            "relative_humidity_2m": 70,
            "wind_speed_10m": 5,
        },
        "daily": {
            "time": ["2026-01-01"],
            "weather_code": [0],
            "temperature_2m_max": [30],
            "temperature_2m_min": [22],
        },
    }
    with patch("backend.tools.weather._aget", new_callable=AsyncMock) as aget:
        aget.side_effect = [fake_geo, fake_forecast]
        r = await get_weather("台北", days=1)
    assert "Taipei" in r or "台北" in r or "28" in r or "晴" in r or "天氣" in r or "溫度" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reminder_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("REMINDERS_FILE", str(tmp_path / "rem.json"))
    a = await manage_reminder("set", text="Alice task", when="30m", user_id="alice")
    b = await manage_reminder("set", text="Bob task", when="1h", user_id="bob")
    assert "Alice" in a or "已" in a or "提醒" in a
    list_a = await manage_reminder("list", user_id="alice")
    list_b = await manage_reminder("list", user_id="bob")
    assert "Alice task" in list_a
    assert "Bob task" not in list_a
    assert "Bob task" in list_b
    assert "Alice task" not in list_b


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reminder_delete_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("REMINDERS_FILE", str(tmp_path / "rem2.json"))
    r = await manage_reminder("delete", reminder_id="nope", user_id="u1")
    assert "找不到" in r or "不存在" in r or "ERROR" in r or "無" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reminder_invalid_action(tmp_path, monkeypatch):
    monkeypatch.setenv("REMINDERS_FILE", str(tmp_path / "rem3.json"))
    r = await manage_reminder("explode", user_id="u1")
    assert "ERROR" in r or "不支援" in r or "action" in r.lower() or "未知" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_and_blocked_tools():
    reg = ToolRegistry()
    r = await reg.execute("not_registered", {})
    assert r.ok is False
    assert r.error_code == "denied"
    with pytest.raises(ValueError):
        reg.register(
            ToolSpec(
                name="bash",
                description="x",
                parameters={"type": "object", "properties": {}},
                handler=AsyncMock(),
            )
        )
    assert "bash" in BLOCKED_TOOL_NAMES


@pytest.mark.unit
@pytest.mark.asyncio
async def test_high_risk_denied():
    reg = ToolRegistry()

    async def h():
        return "secret"

    reg.register(
        ToolSpec(
            name="admin_tool",
            description="x",
            parameters={"type": "object", "properties": {}},
            handler=h,
            risk_level="high",
            required=[],
        )
    )
    r = await reg.execute("admin_tool", {})
    assert r.ok is False
    assert r.error_code == "denied"
    assert reg.openai_tool_definitions() == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_and_long_output(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setenv("MAX_TOOL_OUTPUT_CHARS", "20")

    async def empty():
        return ""

    async def long():
        return "Z" * 500

    reg.register(
        ToolSpec(
            name="empty_t",
            description="e",
            parameters={"type": "object", "properties": {}},
            handler=empty,
            required=[],
        )
    )
    reg.register(
        ToolSpec(
            name="long_t",
            description="l",
            parameters={"type": "object", "properties": {}},
            handler=long,
            required=[],
        )
    )
    e = await reg.execute("empty_t", {})
    assert e.ok is True
    assert "沒有回傳" in e.content or e.content
    l = await reg.execute("long_t", {})
    assert "truncated" in l.content
