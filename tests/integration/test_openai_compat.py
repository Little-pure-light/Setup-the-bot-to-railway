"""OpenAI-compatible /v1 adapter tests (Open WebUI)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from backend.chat_router import ChatResponse
from backend.openai_compat_router import (
    MODEL_ID,
    build_completion_response,
    extract_user_message,
    resolve_conversation_id,
    resolve_user_id,
    strip_internal_protocol,
    OpenAIChatCompletionRequest,
    ChatMessage,
)


def _app():
    from backend.openai_compat_router import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(_app())


# ---------- pure helpers ----------
def test_extract_user_message_last_user():
    msgs = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="first"),
        ChatMessage(role="assistant", content="hi"),
        ChatMessage(role="user", content="second"),
    ]
    assert extract_user_message(msgs) == "second"


def test_extract_user_message_multipart_content():
    msgs = [
        ChatMessage(
            role="user",
            content=[{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}],
        )
    ]
    assert "hello" in extract_user_message(msgs)
    assert "world" in extract_user_message(msgs)


def test_strip_internal_protocol():
    raw = "哈尼\n__XCG_EVENT__{\"type\":\"tool_status\"}\n你好\n__XCG_META__{\"usage\":{}}"
    out = strip_internal_protocol(raw)
    assert "哈尼" in out
    assert "你好" in out
    assert "__XCG_EVENT__" not in out
    assert "__XCG_META__" not in out


def test_resolve_conversation_id_from_header():
    req = MagicMock()
    req.headers = {"x-openwebui-chat-id": "chat-abc-123"}
    body = OpenAIChatCompletionRequest(messages=[], user="u1")
    assert resolve_conversation_id(req, body, "u1") == "chat-abc-123"


def test_resolve_conversation_id_stable_not_per_message():
    req = MagicMock()
    req.headers = {}
    body = OpenAIChatCompletionRequest(
        messages=[ChatMessage(role="user", content="hi")],
        user="user-x",
        chat_id="session-9",
    )
    a = resolve_conversation_id(req, body, "user-x")
    b = resolve_conversation_id(req, body, "user-x")
    assert a == b
    assert a.startswith("owui_") or a == "session-9"
    # body.chat_id takes precedence
    assert a == "session-9"


def test_resolve_user_id_header_priority():
    req = MagicMock()
    req.headers = {"x-user-id": "from-header"}
    body = OpenAIChatCompletionRequest(messages=[], user="from-body")
    assert resolve_user_id(req, body) == "from-header"


def test_build_completion_response_shape():
    data = build_completion_response(content="hello", usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "hello"
    assert data["usage"]["total_tokens"] == 3


# ---------- HTTP endpoints ----------
def test_list_models(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "list"
    assert data["data"][0]["id"] == MODEL_ID
    assert data["data"][0]["owned_by"] == "xiaochenguang"


def test_chat_completions_non_stream(client):
    fake = ChatResponse(
        assistant_message="哈尼～測試回覆",
        emotion_analysis={"dominant_emotion": "joy"},
        conversation_id="c1",
        usage={"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    )

    async def fake_chat(*args, **kwargs):
        return fake

    with patch("backend.chat_router.chat", new=fake_chat):
        r = client.post(
            "/v1/chat/completions",
            json={
                "model": "xiaochenguang",
                "stream": False,
                "messages": [{"role": "user", "content": "你好"}],
                "user": "u-test",
                "chat_id": "chat-stable-1",
            },
            headers={"X-Conversation-Id": "conv-from-header"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "測試回覆" in data["choices"][0]["message"]["content"]
    assert data["usage"]["total_tokens"] == 8


def test_chat_completions_passes_chat_request_fields(client):
    captured = {}

    async def fake_chat(request, background_tasks, stream=True, use_tools=True):
        captured["request"] = request
        captured["stream"] = stream
        captured["use_tools"] = use_tools
        return ChatResponse(
            assistant_message="ok",
            emotion_analysis={},
            conversation_id=request.conversation_id,
        )

    with patch("backend.chat_router.chat", new=fake_chat):
        client.post(
            "/v1/chat/completions",
            json={
                "model": "xiaochenguang",
                "stream": False,
                "messages": [
                    {"role": "user", "content": "msg1"},
                    {"role": "assistant", "content": "a"},
                    {"role": "user", "content": "msg2"},
                ],
                "user": "user-42",
            },
            headers={
                "X-OpenWebUI-Chat-Id": "owui-chat-99",
                "X-User-Id": "header-user",
            },
        )

    assert captured["use_tools"] is True
    assert captured["stream"] is False
    assert captured["request"].user_message == "msg2"
    assert captured["request"].conversation_id == "owui-chat-99"
    assert captured["request"].user_id == "header-user"


def test_chat_completions_stream_sse(client):
    async def plain_stream():
        yield "哈"
        yield "尼\n"
        yield '__XCG_EVENT__{"type":"tool_status","status":"skipped"}\n'
        yield "你好"
        yield '\n__XCG_META__{"usage":{"total_tokens":1}}'

    async def fake_chat(*args, **kwargs):
        return StreamingResponse(plain_stream(), media_type="text/plain")

    with patch("backend.chat_router.chat", new=fake_chat):
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "xiaochenguang",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        ) as r:
            assert r.status_code == 200
            body = "".join(list(r.iter_text()))

    assert "data: " in body
    assert "[DONE]" in body
    assert "__XCG_EVENT__" not in body
    assert "__XCG_META__" not in body
    # content deltas present
    assert "chat.completion.chunk" in body


def test_chat_completions_empty_messages_400(client):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "xiaochenguang", "messages": []},
    )
    assert r.status_code == 400


def test_chat_completions_budget_error_mapped(client):
    from fastapi import HTTPException

    async def fake_chat(*args, **kwargs):
        raise HTTPException(
            status_code=429,
            detail={"error": "budget_exceeded", "message": "budget done"},
        )

    with patch("backend.chat_router.chat", new=fake_chat):
        r = client.post(
            "/v1/chat/completions",
            json={
                "model": "xiaochenguang",
                "stream": False,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 429
    assert "budget" in r.text.lower() or "error" in r.json()


def test_v1_auth_when_secret_set(monkeypatch):
    """main.py middleware protects /v1 when API_SECRET is set."""
    monkeypatch.setenv("API_SECRET", "test-secret-xyz")
    # Re-import path: use main.app with secret
    import importlib
    import main as main_mod

    importlib.reload(main_mod)
    # ensure secret is read
    main_mod.API_SECRET = "test-secret-xyz"

    async def fake_chat(*args, **kwargs):
        return ChatResponse(
            assistant_message="ok",
            emotion_analysis={},
            conversation_id="c",
        )

    with patch("backend.chat_router.chat", new=fake_chat):
        c = TestClient(main_mod.app)
        denied = c.get("/v1/models")
        assert denied.status_code == 401
        ok = c.get("/v1/models", headers={"Authorization": "Bearer test-secret-xyz"})
        assert ok.status_code == 200
        assert ok.json()["data"][0]["id"] == MODEL_ID
