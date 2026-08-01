"""Task 006 C7 — MEMORY_RPC_NAME hardening tests.

The only supported app-path memory RPC is match_memories_v2. Any other value
(unset defaults, legacy 'match_memories', or an arbitrary string) must resolve to
match_memories_v2, so a misconfiguration can never point recall at a legacy/
arbitrary RPC. Deterministic; no real model/DB/service; synthetic values only.
"""
from __future__ import annotations

import pytest

from modules.memory_system import MemorySystem, SUPPORTED_MEMORY_RPC
from tests.mocks.mock_openai import FakeOpenAIClient
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_redis import MockRedisInterface


def _make_memory_system():
    return MemorySystem(
        MockSupabase(),
        FakeOpenAIClient(),
        "xiaochenguang_memories",
        redis_interface=MockRedisInterface(),
    )


def test_supported_rpc_constant_is_v2():
    assert SUPPORTED_MEMORY_RPC == "match_memories_v2"


def test_unset_defaults_to_v2(monkeypatch):
    monkeypatch.delenv("MEMORY_RPC_NAME", raising=False)
    assert _make_memory_system().memory_rpc_name == "match_memories_v2"


def test_explicit_v2_unchanged(monkeypatch):
    monkeypatch.setenv("MEMORY_RPC_NAME", "match_memories_v2")
    assert _make_memory_system().memory_rpc_name == "match_memories_v2"


def test_legacy_value_falls_back_to_v2_with_safe_warning(monkeypatch, capsys):
    monkeypatch.setenv("MEMORY_RPC_NAME", "match_memories")  # legacy
    ms = _make_memory_system()
    assert ms.memory_rpc_name == "match_memories_v2"  # never legacy
    out = capsys.readouterr().out
    assert "MEMORY_RPC_NAME" in out and "回退為 match_memories_v2" in out
    # safe warning must NOT echo the misconfigured value
    assert "match_memories" not in out.replace("match_memories_v2", "")


def test_arbitrary_value_falls_back_to_v2(monkeypatch):
    monkeypatch.setenv("MEMORY_RPC_NAME", "totally_made_up_rpc")
    ms = _make_memory_system()
    assert ms.memory_rpc_name == "match_memories_v2"


def test_empty_value_defaults_to_v2(monkeypatch):
    monkeypatch.setenv("MEMORY_RPC_NAME", "   ")
    assert _make_memory_system().memory_rpc_name == "match_memories_v2"
