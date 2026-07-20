"""整合測試共用 fixtures：重度 Mock，不連正式服務。"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class StreamEventGen:
    """模擬 generate_response_stream 的 async generator。"""

    def __init__(self, chunks: List[Any], fail_at: Optional[int] = None, error: str = "boom"):
        self.chunks = chunks
        self.fail_at = fail_at
        self.error = error

    async def __aiter__(self):
        for i, c in enumerate(self.chunks):
            if self.fail_at is not None and i == self.fail_at:
                raise RuntimeError(self.error)
            if isinstance(c, dict):
                yield c
            else:
                yield {"type": "content", "text": str(c)}
        yield {
            "type": "usage",
            "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
            "model": "gpt-4o-mini",
        }


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.recall_memories = AsyncMock(return_value="")
    mem.get_conversation_history = MagicMock(return_value="")
    mem.save_memory = AsyncMock()
    mem.save_emotional_state = AsyncMock()
    mem._cache_short_term = MagicMock()
    return mem


@pytest.fixture
def mock_prompt_engine():
    pe = MagicMock()
    pe.build_prompt = AsyncMock(
        return_value=(
            [
                {"role": "system", "content": "you are test"},
                {"role": "user", "content": "你好"},
            ],
            {
                "dominant_emotion": "neutral",
                "emotions": {},
                "intensity": 0.5,
                "confidence": 0.5,
            },
        )
    )
    pe.personality_engine = MagicMock()
    pe.personality_engine.learn_from_interaction = MagicMock()
    pe.personality_engine.save_personality = MagicMock()
    return pe


@pytest.fixture
def mock_tracker():
    tracker = MagicMock()
    tracker.check_budget = MagicMock(
        return_value=(True, "ok", {"user": {"cost_usd": 0}, "global": {"cost_usd": 0}})
    )
    tracker.get_user_daily_summary = MagicMock(
        return_value={
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "budget_usd": 10,
            "remaining_usd": 10,
            "calls": 0,
        }
    )
    tracker.record = MagicMock(
        return_value={
            "prompt_tokens": 5,
            "completion_tokens": 7,
            "total_tokens": 12,
            "cost_usd": 0.0001,
            "model": "gpt-4o-mini",
        }
    )
    return tracker


def _build_chat_app():
    from backend.chat_router import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def chat_client(mock_memory, mock_prompt_engine, mock_tracker):
    """
    掛載 chat_router 的 TestClient，預設 Mock 成功聊天路徑。
    """
    async def fake_stream(*args, **kwargs):
        async for x in StreamEventGen(["哈", "尼～", "你好"]):
            yield x

    async def fake_moderate(text, client=None):
        return {
            "flagged": False,
            "blocked": False,
            "categories": {},
            "category_scores": {},
            "flagged_categories": [],
            "model": "test",
        }

    patches = [
        patch("backend.chat_router.get_token_tracker", return_value=mock_tracker),
        patch("backend.chat_router.moderate_text", side_effect=fake_moderate),
        patch("backend.chat_router.MemorySystem", return_value=mock_memory),
        patch("backend.chat_router.PromptEngine", return_value=mock_prompt_engine),
        patch("backend.chat_router.get_openai_client", return_value=MagicMock()),
        patch("backend.chat_router.generate_response_stream", side_effect=fake_stream),
        patch(
            "backend.chat_router.generate_response_with_tools",
            new_callable=AsyncMock,
            return_value={
                "content": "哈尼～你好",
                "tool_calls": [],
                "finish_reason": "stop",
                "raw_message": None,
                "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
                "model": "gpt-4o-mini",
            },
        ),
        patch(
            "backend.chat_router.generate_response",
            new_callable=AsyncMock,
            return_value={
                "content": "哈尼～你好",
                "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
                "model": "gpt-4o-mini",
            },
        ),
        patch("backend.chat_router.get_tool_registry"),
        patch("backend.chat_router.get_openai_tool_definitions", return_value=[]),
        patch("backend.chat_router.get_core_controller", new_callable=AsyncMock),
    ]

    started = []
    try:
        for p in patches:
            started.append(p.start())
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None

        app = _build_chat_app()
        with TestClient(app) as client:
            yield client, mock_memory, mock_tracker
    finally:
        for p in reversed(started):
            p.stop()
