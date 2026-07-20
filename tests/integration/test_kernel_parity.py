"""Legacy flag off 時行為不變；kernel on 時仍回傳相容結構。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.integration.conftest import StreamEventGen


def _app():
    from backend.chat_router import router

    a = FastAPI()
    a.include_router(router, prefix="/api")
    return a


PAYLOAD = {
    "user_message": "你好",
    "conversation_id": "parity-c",
    "user_id": "parity-u",
}


@pytest.fixture
def patches(mock_memory, mock_prompt_engine, mock_tracker, monkeypatch):
    monkeypatch.setenv("AI_KERNEL_ENABLED", "false")
    monkeypatch.setenv("AI_KERNEL_SHADOW_MODE", "false")

    async def ok_stream(*a, **k):
        async for x in StreamEventGen(["哈", "尼"]):
            yield x

    async def ok_mod(text, client=None):
        return {"blocked": False, "flagged": False, "flagged_categories": []}

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
            "content": "哈尼",
            "tool_calls": [],
            "finish_reason": "stop",
            "raw_message": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": "gpt-4o-mini",
        },
    ), patch(
        "backend.chat_router.generate_response",
        new_callable=AsyncMock,
        return_value={
            "content": "哈尼",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
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
        yield


@pytest.mark.integration
def test_legacy_still_works_when_kernel_off(patches):
    with TestClient(_app()) as client:
        r = client.post("/api/chat?stream=false&use_tools=false", json=PAYLOAD)
    assert r.status_code == 200
    assert r.json().get("assistant_message")
    assert r.json().get("conversation_id") == "parity-c"
