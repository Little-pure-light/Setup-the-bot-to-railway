"""Memory V2 Strangler — coexist with V1; chat still works when V2 on/off."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.chat_router import ChatResponse, router as chat_router
from backend.modules.memory_manager import MemoryManager, LegacyMemoryAdapter
from tests.mocks.mock_openai import FakeOpenAIClient
from tests.mocks.mock_supabase import MockSupabase


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("MEMORY_V2_ENABLED", "false")
    app = FastAPI()
    app.include_router(chat_router, prefix="/api")
    return TestClient(app)


def test_v1_path_unchanged_default(monkeypatch):
    monkeypatch.setenv("MEMORY_V2_ENABLED", "false")
    from backend.chat_router import _build_memory_system

    ms = MagicMock()
    with patch("backend.chat_router.MemorySystem", return_value=ms) as p:
        out = _build_memory_system(MagicMock(), "xiaochenguang_memories")
    assert out is ms
    p.assert_called()


def test_v2_path_returns_legacy_adapter(monkeypatch):
    monkeypatch.setenv("MEMORY_V2_ENABLED", "true")
    from backend.chat_router import _build_memory_system
    from modules.memory_system import MemorySystem

    sb = MockSupabase()
    oa = FakeOpenAIClient()

    def fake_ms(*a, **k):
        return MemorySystem(sb, oa, "xiaochenguang_memories")

    with patch("backend.chat_router.MemorySystem", side_effect=fake_ms):
        out = _build_memory_system(oa, "xiaochenguang_memories")
    assert isinstance(out, LegacyMemoryAdapter)


@pytest.mark.asyncio
async def test_v2_manager_does_not_drop_conversation(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORY_V2_ENABLED", "true")
    from modules.memory_system import MemorySystem
    from backend.modules.graph_manager import GraphManager

    sb = MockSupabase()
    oa = FakeOpenAIClient()
    v1 = MemorySystem(sb, oa, "xiaochenguang_memories")
    mgr = MemoryManager(
        v1, graph=GraphManager(user_id="u1", storage_path=str(tmp_path / "g.json"))
    )
    await mgr.save(
        user_message="跨裝置測試訊息",
        bot_response="收到",
        conversation_id="conv-keep",
        user_id="user-keep",
    )
    conv_rows = [
        r
        for r in sb.table("xiaochenguang_memories").rows
        if r.get("memory_type") == "conversation"
    ]
    assert len(conv_rows) >= 1
    assert conv_rows[0]["user_id"] == "user-keep"
    assert conv_rows[0]["conversation_id"] == "conv-keep"


def test_chat_api_still_works_with_v2_flag(monkeypatch):
    """Integration: mock pipeline; V2 adapter must still answer via /api/chat."""
    monkeypatch.setenv("MEMORY_V2_ENABLED", "true")
    monkeypatch.setenv("MODERATION_ENABLED", "false")

    from modules.memory_system import MemorySystem

    sb = MockSupabase()
    oa = FakeOpenAIClient()

    def make_v1(*a, **k):
        return MemorySystem(sb, oa, "xiaochenguang_memories")

    mock_tracker = MagicMock()
    mock_tracker.check_budget.return_value = (True, "ok", {"user": {}, "global": {}})
    mock_tracker.get_user_daily_summary.return_value = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0,
        "budget_usd": 10,
        "remaining_usd": 10,
        "calls": 0,
    }
    mock_tracker.record.return_value = {
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
        "cost_usd": 0,
    }

    pe = MagicMock()
    pe.build_prompt = AsyncMock(
        return_value=(
            [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}],
            {"dominant_emotion": "neutral", "emotions": {}, "intensity": 0.5, "confidence": 0.5},
        )
    )
    pe.personality_engine = MagicMock()

    async def fake_tools(*a, **k):
        return {
            "content": "你好呀",
            "tool_calls": [],
            "finish_reason": "stop",
            "raw_message": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": "gpt-4o-mini",
        }

    async def fake_gen(*a, **k):
        return {
            "content": "你好呀",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": "gpt-4o-mini",
        }

    app = FastAPI()
    app.include_router(chat_router, prefix="/api")

    with patch("backend.chat_router.MemorySystem", side_effect=make_v1), patch(
        "backend.chat_router.get_token_tracker", return_value=mock_tracker
    ), patch("backend.chat_router.get_openai_client", return_value=oa), patch(
        "backend.chat_router.moderate_text",
        new=AsyncMock(
            return_value={
                "blocked": False,
                "flagged": False,
                "categories": {},
                "flagged_categories": [],
            }
        ),
    ), patch("backend.chat_router.PromptEngine", return_value=pe), patch(
        "backend.chat_router.generate_response_with_tools", new=fake_tools
    ), patch("backend.chat_router.generate_response", new=fake_gen), patch(
        "backend.chat_router.get_tool_registry"
    ) as reg, patch(
        "backend.chat_router.get_openai_tool_definitions", return_value=[]
    ), patch(
        "backend.chat_router.run_post_chat_tasks", new=AsyncMock()
    ), patch(
        "backend.chat_router._try_kernel_chat", new=AsyncMock(return_value=None)
    ):
        reg.return_value = MagicMock()
        client = TestClient(app)
        r = client.post(
            "/api/chat?stream=false&use_tools=false",
            json={
                "user_message": "你好",
                "conversation_id": "v2-int-1",
                "user_id": "u-v2",
            },
        )
    assert r.status_code == 200
    assert r.json().get("assistant_message")
    # conversation persisted via V2 manager → V1
    assert any(
        row.get("conversation_id") == "v2-int-1"
        for row in sb.table("xiaochenguang_memories").rows
    )
