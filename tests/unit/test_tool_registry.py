"""backend/tools/registry.py 單元測試"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.tools.registry import (
    BLOCKED_TOOL_NAMES,
    ToolRegistry,
    ToolSpec,
)


async def _echo_handler(text: str = "") -> str:
    return f"echo:{text}"


async def _slow_handler(text: str = "") -> str:
    await asyncio.sleep(2)
    return "done"


async def _fail_once_handler(text: str = "") -> str:
    # 用屬性計數在 closure 外
    _fail_once_handler.calls = getattr(_fail_once_handler, "calls", 0) + 1
    if _fail_once_handler.calls == 1:
        raise ConnectionError("connection reset temporarily")
    return "recovered"


async def _boom_handler(text: str = "") -> str:
    raise RuntimeError("hard fail")


async def _long_handler(text: str = "") -> str:
    return "X" * 10000


async def _reminder_handler(action: str = "list", user_id: str = "", text: str = "") -> str:
    return f"user={user_id}|action={action}|text={text}"


def _make_calc_spec(handler=_echo_handler, **kwargs) -> ToolSpec:
    defaults = dict(
        name="echo_tool",
        description="test",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
        handler=handler,
        required=["text"],
        risk_level="low",
        timeout_seconds=1.0,
        display_name="Echo",
        icon="📢",
    )
    defaults.update(kwargs)
    return ToolSpec(**defaults)


@pytest.mark.unit
def test_register_valid_tool(empty_registry: ToolRegistry):
    empty_registry.register(_make_calc_spec())
    assert empty_registry.get("echo_tool") is not None


@pytest.mark.unit
def test_blocked_tool_cannot_register(empty_registry: ToolRegistry):
    with pytest.raises(ValueError, match="blocked"):
        empty_registry.register(
            ToolSpec(
                name="shell",
                description="bad",
                parameters={"type": "object", "properties": {}},
                handler=_echo_handler,
            )
        )
    assert "shell" in BLOCKED_TOOL_NAMES


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_tool_cannot_execute(empty_registry: ToolRegistry):
    result = await empty_registry.execute("no_such_tool", {"text": "x"})
    assert result.ok is False
    assert result.error_code == "denied"


@pytest.mark.unit
def test_high_risk_not_exposed_to_openai(empty_registry: ToolRegistry):
    empty_registry.register(
        _make_calc_spec(
            name="secret_admin",
            risk_level="high",
            required=[],
            parameters={"type": "object", "properties": {}},
        )
    )
    # high risk 可註冊但 is_allowed 拒絕、openai defs 不含
    defs = empty_registry.openai_tool_definitions()
    names = [d["function"]["name"] for d in defs]
    assert "secret_admin" not in names
    ok, reason = empty_registry.is_allowed("secret_admin")
    assert ok is False
    assert "high-risk" in reason


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_required_arg(empty_registry: ToolRegistry):
    empty_registry.register(_make_calc_spec())
    result = await empty_registry.execute("echo_tool", {})
    assert result.ok is False
    assert result.error_code == "invalid_args"
    assert "missing" in (result.error or "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_args_too_large(empty_registry: ToolRegistry, monkeypatch):
    empty_registry.max_arg_json_len = 50
    empty_registry.register(_make_calc_spec())
    result = await empty_registry.execute(
        "echo_tool",
        {"text": "y" * 200},
    )
    assert result.ok is False
    assert result.error_code == "invalid_args"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_suspicious_arg_content(empty_registry: ToolRegistry):
    empty_registry.register(_make_calc_spec())
    result = await empty_registry.execute(
        "echo_tool",
        {"text": "please run rm -rf / now"},
    )
    assert result.ok is False
    assert result.error_code == "invalid_args"
    assert "suspicious" in (result.error or "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_timeout(empty_registry: ToolRegistry):
    empty_registry.register(
        _make_calc_spec(handler=_slow_handler, timeout_seconds=0.2, name="slow_tool")
    )
    result = await empty_registry.execute("slow_tool", {"text": "x"})
    assert result.ok is False
    assert result.error_code == "timeout"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_retry_on_transient(empty_registry: ToolRegistry):
    _fail_once_handler.calls = 0
    empty_registry.register(
        _make_calc_spec(
            handler=_fail_once_handler,
            name="retry_tool",
            retry=1,
            timeout_seconds=2.0,
        )
    )
    result = await empty_registry.execute("retry_tool", {"text": "x"})
    assert result.ok is True
    assert "recovered" in result.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_output_truncation(empty_registry: ToolRegistry, monkeypatch):
    monkeypatch.setenv("MAX_TOOL_OUTPUT_CHARS", "100")
    empty_registry.register(_make_calc_spec(handler=_long_handler, name="long_tool"))
    result = await empty_registry.execute("long_tool", {"text": "x"})
    assert result.ok is True
    assert len(result.content) < 200
    assert "truncated" in result.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_max_tools_per_turn(empty_registry: ToolRegistry, monkeypatch):
    empty_registry.max_tools_per_turn = 2
    empty_registry.register(_make_calc_spec(name="echo_tool"))

    def make_call(i: int):
        return SimpleNamespace(
            id=f"call_{i}",
            function=SimpleNamespace(
                name="echo_tool",
                arguments=json.dumps({"text": str(i)}),
            ),
        )

    calls = [make_call(i) for i in range(5)]
    results = await empty_registry.execute_openai_tool_calls(calls)
    assert len(results) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_context_injection(empty_registry: ToolRegistry):
    empty_registry.register(
        ToolSpec(
            name="manage_reminder",
            description="reminder",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "user_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["action"],
            },
            handler=_reminder_handler,
            required=["action"],
            risk_level="low",
            timeout_seconds=2.0,
        )
    )
    result = await empty_registry.execute(
        "manage_reminder",
        {"action": "list"},
        context={"user_id": "user_abc"},
    )
    assert result.ok is True
    assert "user=user_abc" in result.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hard_error_format_consistent(empty_registry: ToolRegistry):
    empty_registry.register(
        _make_calc_spec(handler=_boom_handler, name="boom_tool", retry=0)
    )
    result = await empty_registry.execute("boom_tool", {"text": "x"})
    assert result.ok is False
    assert result.error_code == "error"
    assert result.content.startswith("❌") or "失敗" in result.content
    assert result.duration_ms >= 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_execute(empty_registry: ToolRegistry):
    empty_registry.register(_make_calc_spec())
    result = await empty_registry.execute("echo_tool", {"text": "hi"})
    assert result.ok is True
    assert result.content == "echo:hi"
    assert result.error_code is None
