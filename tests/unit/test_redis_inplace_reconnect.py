"""
Integration: module-level RedisInterface refs keep identity after reconnect;
store_short_term hits the NEW real client, not the old RedisMock.
Also: real disconnect → recovery via /ready path.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import backend.redis_interface as ri
from backend.redis_interface import (
    get_shared_redis_interface,
    maybe_reconnect_redis,
    redis_ping_status,
)
from backend.redis_mock import RedisMock
from backend.modules.reflection_storage import ReflectionStorage
from modules.memory_system import MemorySystem
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_openai import FakeOpenAIClient


@pytest.fixture(autouse=True)
def _reset():
    ri._shared_interface = None
    ri._redis_mode = "none"
    ri._last_reconnect_attempt = 0.0
    ri._last_error_type = None
    yield
    ri._shared_interface = None
    ri._last_reconnect_attempt = 0.0


def test_inplace_reconnect_old_refs_use_new_client(monkeypatch):
    """A–F: start mock → hold refs → recover → store uses real fake."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REDIS_RECONNECT_COOLDOWN_SECONDS", "1")

    calls = {"n": 0}
    real_client = MagicMock(name="RealRedisClient")
    real_client.ping.return_value = True
    stored = {}

    def real_set(key, value, ex=None, **kwargs):
        stored[key] = value
        return True

    def real_expire(key, ttl):
        stored[f"ttl:{key}"] = ttl
        return True

    real_client.set.side_effect = real_set
    real_client.expire.side_effect = real_expire
    real_client.get.return_value = None

    def fake_create():
        calls["n"] += 1
        if calls["n"] == 1:
            ri._last_error_type = "ConnectionError"
            return RedisMock(), "mock", "ConnectionError"
        ri._last_error_type = None
        return real_client, "real", None

    with patch.object(ri, "create_redis_client", side_effect=fake_create):
        # A. start mock
        shared = get_shared_redis_interface(force_refresh=True)
        assert shared.mode == "mock"
        old_mock = shared.get_client()
        assert isinstance(old_mock, RedisMock)

        # B. pre-existing holders (simulates chat_router module-level + services)
        chat_router_ref = shared  # same object as module-level
        ms = MemorySystem(
            MockSupabase(),
            FakeOpenAIClient(),
            "xiaochenguang_memories",
            redis_interface=chat_router_ref,
        )
        reflection = ReflectionStorage(
            redis_interface=chat_router_ref,
            supabase_client=None,
            pinecone_handler=None,
        )
        assert ms.redis is chat_router_ref
        assert reflection.redis is chat_router_ref
        assert chat_router_ref is shared

        # C. recover via ready reconnect
        ri._last_reconnect_attempt = 0.0
        after = maybe_reconnect_redis(force=True)
        assert after is shared  # same object identity
        assert after.mode == "real"
        assert after.get_client() is real_client
        assert after.get_client() is not old_mock

        # D–E. old reference store_short_term writes to real client
        ok = chat_router_ref.store_short_term(
            "conv-old-ref",
            {
                "messages": [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "yo"},
                ]
            },
        )
        assert ok is True
        assert any(k.startswith("conv:conv-old-ref:") for k in stored)
        # ensure not only on old mock storage
        assert "conv:conv-old-ref:latest" in stored or any(
            "conv-old-ref" in str(k) for k in stored
        )

        # F. reflection storage still uses same iface → real client
        assert reflection.redis is shared
        assert reflection.redis.mode == "real"
        assert reflection.redis.get_client() is real_client


def test_real_disconnect_recovers_via_ping_status(monkeypatch):
    """Real in use → ping fails → reconnect can become real again (not stuck ping_fail)."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REDIS_RECONNECT_COOLDOWN_SECONDS", "1")

    state = {"phase": "up"}

    class Flaky:
        def __init__(self, label):
            self.label = label
            self.sets = []

        def ping(self):
            if state["phase"] == "down" and self.label == "first":
                raise ConnectionError("broken")
            return True

        def set(self, *a, **k):
            self.sets.append(a)
            return True

        def expire(self, *a, **k):
            return True

        def get(self, *a, **k):
            return None

    clients = {"n": 0}

    def fake_create():
        clients["n"] += 1
        if clients["n"] == 1:
            return Flaky("first"), "real", None
        return Flaky("second"), "real", None

    with patch.object(ri, "create_redis_client", side_effect=fake_create):
        ri._shared_interface = None
        iface = get_shared_redis_interface(force_refresh=True)
        assert iface.mode == "real"
        holder = iface  # old reference
        # healthy
        st1 = redis_ping_status()
        assert st1["status"] == "ping_ok"
        # break first client
        state["phase"] = "down"
        ri._last_reconnect_attempt = 0.0
        st2 = redis_ping_status()
        # should recover to second real client
        assert st2["status"] == "ping_ok"
        assert st2["mode"] == "real"
        assert holder is iface
        assert holder.get_client().label == "second"
        # old ref still works
        assert holder.store_short_term("c-recov", {"messages": []}) is True
