"""P1-03: /api/chat 整合測試（全 Mock，不連正式服務）"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.integration.conftest import StreamEventGen


def _app():
    from backend.chat_router import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


PAYLOAD = {
    "user_message": "你好",
    "conversation_id": "test-conversation",
    "user_id": "test-user",
    "ai_id": "xiaochenguang_v1",
}


@pytest.fixture
def base_patches(mock_memory, mock_prompt_engine, mock_tracker):
    async def ok_stream(*a, **k):
        async for x in StreamEventGen(["你好呀", " 😊"]):
            yield x

    async def ok_mod(text, client=None):
        return {
            "flagged": False,
            "blocked": False,
            "categories": {},
            "flagged_categories": [],
            "model": "test",
        }

    with patch("backend.chat_router.get_token_tracker", return_value=mock_tracker), patch(
        "backend.chat_router.moderate_text", side_effect=ok_mod
    ), patch("backend.chat_router.MemorySystem", return_value=mock_memory), patch(
        "backend.chat_router.PromptEngine", return_value=mock_prompt_engine
    ), patch(
        "backend.chat_router.get_openai_client", return_value=MagicMock()
    ), patch(
        "backend.chat_router.generate_response_stream", side_effect=ok_stream
    ), patch(
        "backend.chat_router.generate_response_with_tools",
        new_callable=AsyncMock,
        return_value={
            "content": "你好呀",
            "tool_calls": [],
            "finish_reason": "stop",
            "raw_message": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            "model": "gpt-4o-mini",
        },
    ), patch(
        "backend.chat_router.generate_response",
        new_callable=AsyncMock,
        return_value={
            "content": "你好呀",
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            "model": "gpt-4o-mini",
        },
    ), patch(
        "backend.chat_router.get_openai_tool_definitions", return_value=[]
    ), patch(
        "backend.chat_router.get_core_controller", new_callable=AsyncMock
    ):
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        yield mock_memory, mock_tracker


@pytest.mark.integration
def test_normal_chat_non_stream(base_patches):
    mock_memory, mock_tracker = base_patches
    with TestClient(_app()) as client:
        r = client.post("/api/chat?stream=false&use_tools=false", json=PAYLOAD)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("assistant_message")
    assert data.get("conversation_id") == "test-conversation"
    assert "sk-" not in r.text
    assert "test-key" not in r.text.lower() or "api" not in r.text.lower()
    mock_memory.save_memory.assert_awaited()


@pytest.mark.integration
def test_invalid_request_missing_fields(base_patches):
    with TestClient(_app()) as client:
        r = client.post("/api/chat?stream=false", json={"user_message": "hi"})
    assert r.status_code == 422


@pytest.mark.integration
def test_budget_exceeded_returns_429(base_patches, mock_memory, mock_prompt_engine):
    _, mock_tracker = base_patches
    mock_tracker.check_budget.return_value = (
        False,
        "使用者今日預算已用盡",
        {"user": {"cost_usd": 99}},
    )
    openai_calls = []

    async def should_not_stream(*a, **k):
        openai_calls.append(1)
        if False:
            yield {"type": "content", "text": "x"}

    with patch("backend.chat_router.generate_response_stream", side_effect=should_not_stream), patch(
        "backend.chat_router.get_token_tracker", return_value=mock_tracker
    ), patch("backend.chat_router.MemorySystem", return_value=mock_memory), patch(
        "backend.chat_router.PromptEngine", return_value=mock_prompt_engine
    ), patch("backend.chat_router.get_openai_client", return_value=MagicMock()), patch(
        "backend.chat_router.moderate_text",
        new_callable=AsyncMock,
        return_value={"blocked": False, "flagged": False, "flagged_categories": []},
    ):
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app()) as client:
            r = client.post("/api/chat?stream=false", json=PAYLOAD)
    assert r.status_code == 429
    body = r.json()
    detail = body.get("detail") or body
    if isinstance(detail, dict):
        assert detail.get("error") == "budget_exceeded"
    assert openai_calls == []
    mock_memory.save_memory.assert_not_called()


@pytest.mark.integration
def test_moderation_blocked_non_stream(base_patches, mock_memory, mock_prompt_engine, mock_tracker):
    async def blocked_mod(text, client=None):
        return {
            "flagged": True,
            "blocked": True,
            "flagged_categories": ["violence"],
            "categories": {"violence": True},
        }

    with patch("backend.chat_router.moderate_text", side_effect=blocked_mod), patch(
        "backend.chat_router.get_token_tracker", return_value=mock_tracker
    ), patch("backend.chat_router.MemorySystem", return_value=mock_memory), patch(
        "backend.chat_router.PromptEngine", return_value=mock_prompt_engine
    ), patch("backend.chat_router.get_openai_client", return_value=MagicMock()), patch(
        "backend.chat_router.generate_response", new_callable=AsyncMock
    ) as gen:
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app()) as client:
            r = client.post("/api/chat?stream=false", json=PAYLOAD)
    assert r.status_code == 400
    assert "blocked" in r.text.lower() or "審核" in r.text or "安全" in r.text
    gen.assert_not_called()
    mock_memory.save_memory.assert_not_called()


@pytest.mark.integration
def test_openai_failure_no_secret_leak(base_patches, mock_memory, mock_prompt_engine, mock_tracker):
    async def boom_stream(*a, **k):
        yield {"type": "content", "text": "[ERROR] Streaming 失敗: simulated-500"}
        yield {
            "type": "usage",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "model": "gpt-4o-mini",
        }

    with patch("backend.chat_router.generate_response_stream", side_effect=boom_stream), patch(
        "backend.chat_router.get_token_tracker", return_value=mock_tracker
    ), patch("backend.chat_router.MemorySystem", return_value=mock_memory), patch(
        "backend.chat_router.PromptEngine", return_value=mock_prompt_engine
    ), patch("backend.chat_router.get_openai_client", return_value=MagicMock()), patch(
        "backend.chat_router.moderate_text",
        new_callable=AsyncMock,
        return_value={"blocked": False, "flagged": False, "flagged_categories": []},
    ), patch(
        "backend.chat_router.get_openai_tool_definitions", return_value=[]
    ):
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app()) as client:
            r = client.post("/api/chat?stream=true&use_tools=false", json=PAYLOAD)
            assert r.status_code == 200
            text = r.text
    assert "sk-proj" not in text
    assert "OPENAI_API_KEY" not in text
    assert "test-key-not-real" not in text


@pytest.mark.integration
def test_main_health_liveness_endpoints():
    """不依賴 chat 的健康端點（main.py）"""
    from main import app

    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "healthy"
        assert "sk-" not in r.text

        r2 = client.get("/api/health")
        assert r2.status_code == 200
        assert r2.json().get("status") == "healthy"


@pytest.mark.integration
def test_secret_not_in_error_body(base_patches, mock_memory, mock_prompt_engine, mock_tracker):
    async def fail_build(*a, **k):
        raise RuntimeError("OpenAI key sk-proj-SECRETVALUE leaked?")

    with patch("backend.chat_router.PromptEngine", return_value=mock_prompt_engine), patch.object(
        mock_prompt_engine, "build_prompt", side_effect=fail_build
    ), patch("backend.chat_router.get_token_tracker", return_value=mock_tracker), patch(
        "backend.chat_router.MemorySystem", return_value=mock_memory
    ), patch(
        "backend.chat_router.get_openai_client", return_value=MagicMock()
    ), patch(
        "backend.chat_router.moderate_text",
        new_callable=AsyncMock,
        return_value={"blocked": False, "flagged": False, "flagged_categories": []},
    ):
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app(), raise_server_exceptions=False) as client:
            r = client.post("/api/chat?stream=false", json=PAYLOAD)
    # 500 or handled — body must not contain the fake secret
    assert "sk-proj-SECRETVALUE" not in r.text
