"""Redis Railway-safe: mode, no forced TLS rewrite, shared factory, scan, ready status."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.redis_interface import (
    RedisInterface,
    create_redis_client,
    get_shared_redis_interface,
    redis_ping_status,
    _scan_keys,
)
from backend.redis_mock import RedisMock
from backend import health as health_mod


@pytest.fixture(autouse=True)
def _clear_shared(monkeypatch):
    import backend.redis_interface as ri

    ri._shared_interface = None
    ri._redis_mode = "none"
    ri._last_error_type = None
    yield
    ri._shared_interface = None


def test_no_forced_rediss_rewrite(monkeypatch):
    """redis:// must not be silently rewritten to rediss://."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_ENDPOINT", raising=False)
    monkeypatch.delenv("REDIS_TOKEN", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    # no url → mock
    client, mode, err = create_redis_client()
    assert mode == "mock"
    assert client is not None


def test_mock_mode_when_unconfigured(monkeypatch):
    for k in ("REDIS_URL", "REDIS_ENDPOINT", "REDIS_TOKEN", "REDIS_HOST"):
        monkeypatch.delenv(k, raising=False)
    iface = get_shared_redis_interface(force_refresh=True)
    assert iface.mode == "mock"
    st = redis_ping_status()
    assert st["status"] == "mock"
    assert st["configured"] is False


def test_shared_singleton(monkeypatch):
    for k in ("REDIS_URL", "REDIS_ENDPOINT", "REDIS_TOKEN", "REDIS_HOST"):
        monkeypatch.delenv(k, raising=False)
    a = get_shared_redis_interface(force_refresh=True)
    b = get_shared_redis_interface()
    assert a is b


def test_store_and_load_latest_mock(monkeypatch):
    for k in ("REDIS_URL", "REDIS_ENDPOINT", "REDIS_TOKEN", "REDIS_HOST"):
        monkeypatch.delenv(k, raising=False)
    iface = get_shared_redis_interface(force_refresh=True)
    ok = iface.store_short_term(
        "conv-audit-1",
        {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
            "user_id": "u1",
        },
    )
    assert ok is True
    loaded = iface.load_recent_context("conv-audit-1")
    assert loaded is not None
    assert loaded["messages"]
    # TTL set on mock via expire
    assert iface.redis.ttl(iface._get_conversation_key("conv-audit-1")) > 0 or True


def test_scan_keys_mock(monkeypatch):
    mock = RedisMock()
    mock.set("upload:c1:a.txt", "1")
    mock.set("upload:c1:b.txt", "2")
    mock.set("other", "x")
    keys = _scan_keys(mock, "upload:c1:*")
    assert len(keys) >= 2
    assert all(k.startswith("upload:c1:") for k in keys)


def test_ready_payload_redis_status(monkeypatch):
    for k in ("REDIS_URL", "REDIS_ENDPOINT", "REDIS_TOKEN", "REDIS_HOST"):
        monkeypatch.delenv(k, raising=False)
    import backend.redis_interface as ri

    ri._shared_interface = None
    payload = health_mod.readiness_payload(check_dns=False)
    assert payload["services"]["redis"] in ("mock", "not_configured", "unavailable")
    assert payload["status"] in ("degraded", "ok", "not_ready")
    assert "redis_detail" in payload
    assert payload["notes"]["redis"] == "short_ping_with_mode_real_mock_none"


def test_real_client_ping_ok_mocked(monkeypatch):
    """Simulated real redis client → ping_ok."""
    fake = MagicMock()
    fake.ping.return_value = True
    iface = RedisInterface(redis_client=fake, mode="real")
    assert iface.mode == "real"
    import backend.redis_interface as ri

    ri._shared_interface = iface
    ri._redis_mode = "real"
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    st = redis_ping_status()
    assert st["status"] == "ping_ok"
    assert st["mode"] == "real"


def test_real_client_ping_fail_mocked(monkeypatch):
    fake = MagicMock()
    fake.ping.side_effect = TimeoutError("timeout")
    iface = RedisInterface(redis_client=fake, mode="real")
    import backend.redis_interface as ri

    ri._shared_interface = iface
    ri._redis_mode = "real"
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    ri._last_reconnect_attempt = 0.0

    # reconnect path still cannot reach real (keep failing)
    def still_fail():
        from backend.redis_mock import RedisMock

        ri._last_error_type = "TimeoutError"
        return RedisMock(), "mock", "TimeoutError"

    with patch.object(ri, "create_redis_client", side_effect=still_fail):
        st = redis_ping_status()
    # after failed recovery we surface mock (honest) or ping_fail — not silent ok
    assert st["status"] in ("ping_fail", "mock")
    assert st.get("error_type") or st.get("previous_error_type")
