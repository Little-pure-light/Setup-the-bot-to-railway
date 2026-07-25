"""Stream first-token, LLM stage timing, Redis mock→real reconnect."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.request_timing import RequestTimer as RT
from backend.chat_router import TOOL_EVENT_PREFIX, USAGE_META_PREFIX
from backend.redis_interface import (
    get_shared_redis_interface,
    maybe_reconnect_redis,
    redis_ping_status,
)
import backend.redis_interface as ri


@pytest.fixture(autouse=True)
def _reset_redis_singleton():
    ri._shared_interface = None
    ri._redis_mode = "none"
    ri._last_reconnect_attempt = 0.0
    ri._last_error_type = None
    yield
    ri._shared_interface = None
    ri._last_reconnect_attempt = 0.0


def test_first_token_only_once_and_ignores_tool_meta():
    t = RT(request_id="rid1", conversation_id="c1")
    assert t.first_token_ms is None
    # tool / empty / meta must not set
    assert t.note_displayable_text("", tool_prefix=TOOL_EVENT_PREFIX, meta_prefix=USAGE_META_PREFIX) is False
    assert t.note_displayable_text(
        TOOL_EVENT_PREFIX + '{"type":"tool"}',
        tool_prefix=TOOL_EVENT_PREFIX,
        meta_prefix=USAGE_META_PREFIX,
    ) is False
    assert t.note_displayable_text(
        USAGE_META_PREFIX + "{}",
        tool_prefix=TOOL_EVENT_PREFIX,
        meta_prefix=USAGE_META_PREFIX,
    ) is False
    assert t.first_token_ms is None
    # real content
    assert t.note_displayable_text(
        "你好",
        tool_prefix=TOOL_EVENT_PREFIX,
        meta_prefix=USAGE_META_PREFIX,
    ) is True
    assert t.first_token_ms is not None
    first = t.first_token_ms
    # second content ignored for first_token
    assert t.note_displayable_text(
        "世界",
        tool_prefix=TOOL_EVENT_PREFIX,
        meta_prefix=USAGE_META_PREFIX,
    ) is False
    assert t.first_token_ms == first


def test_llm_stages_record_independent_ms():
    t = RT(request_id="r2", conversation_id="c2")
    t.record_stage("llm_tool_call", 12)
    t.record_stage("llm_stream", 34)
    t.record_stage("llm_non_stream", 56)
    names = [s["stage"] for s in t.stages]
    assert "llm_tool_call" in names
    assert "llm_stream" in names
    assert "llm_non_stream" in names
    by = {s["stage"]: s["ms"] for s in t.stages}
    assert by["llm_tool_call"] == 12
    assert by["llm_stream"] == 34
    assert by["llm_non_stream"] == 56
    t.mark_first_token()
    t.mark_complete()
    d = t.as_dict()
    assert d["first_token_ms"] is not None
    assert d["complete_ms"] is not None


def test_redis_reconnect_mock_to_real(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REDIS_RECONNECT_COOLDOWN_SECONDS", "1")

    calls = {"n": 0}

    def fake_create():
        calls["n"] += 1
        if calls["n"] == 1:
            # first: fail → mock
            from backend.redis_mock import RedisMock

            ri._last_error_type = "ConnectionError"
            return RedisMock(), "mock", "ConnectionError"
        # second: real
        fake = MagicMock()
        fake.ping.return_value = True
        ri._last_error_type = None
        return fake, "real", None

    with patch.object(ri, "create_redis_client", side_effect=fake_create):
        ri._shared_interface = None
        iface1 = get_shared_redis_interface(force_refresh=True)
        assert iface1.mode == "mock"
        # force reconnect immediately
        ri._last_reconnect_attempt = 0.0
        iface2 = maybe_reconnect_redis(force=True)
        assert iface2 is iface1  # in-place: same object
        assert iface2.mode == "real"
        assert calls["n"] >= 2


def test_redis_reconnect_respects_cooldown(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REDIS_RECONNECT_COOLDOWN_SECONDS", "60")

    calls = {"n": 0}

    def fake_create():
        calls["n"] += 1
        from backend.redis_mock import RedisMock

        ri._last_error_type = "ConnectionError"
        return RedisMock(), "mock", "ConnectionError"

    with patch.object(ri, "create_redis_client", side_effect=fake_create):
        ri._shared_interface = None
        ri._last_reconnect_attempt = 0.0
        get_shared_redis_interface(force_refresh=True)
        n1 = calls["n"]
        maybe_reconnect_redis(force=False)  # should attempt once
        n2 = calls["n"]
        assert n2 > n1
        n3 = calls["n"]
        maybe_reconnect_redis(force=False)  # within cooldown — no new create
        assert calls["n"] == n3 or calls["n"] == n2  # no extra refresh
        # ensure we didn't spam: at most one reconnect batch after first
        assert calls["n"] <= n1 + 1


def test_ready_triggers_reconnect_path(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REDIS_RECONNECT_COOLDOWN_SECONDS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test")
    monkeypatch.setenv("READY_CHECK_SUPABASE_DNS", "false")

    state = {"n": 0}

    def fake_create():
        state["n"] += 1
        if state["n"] == 1:
            from backend.redis_mock import RedisMock

            ri._last_error_type = "ConnectionError"
            return RedisMock(), "mock", "ConnectionError"
        fake = MagicMock()
        fake.ping.return_value = True
        ri._last_error_type = None
        return fake, "real", None

    with patch.object(ri, "create_redis_client", side_effect=fake_create):
        ri._shared_interface = None
        ri._last_reconnect_attempt = 0.0
        get_shared_redis_interface(force_refresh=True)
        assert get_shared_redis_interface().mode == "mock"
        ri._last_reconnect_attempt = 0.0
        st = redis_ping_status()
        assert st["mode"] == "real" or st["status"] == "ping_ok"
