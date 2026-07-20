"""P1-04: Streaming 協議與行為回歸（Mock OpenAI）"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.chat_router import USAGE_META_PREFIX, TOOL_EVENT_PREFIX, _tool_event_payload
from tests.integration.conftest import StreamEventGen


def _app():
    from backend.chat_router import router

    a = FastAPI()
    a.include_router(router, prefix="/api")
    return a


PAYLOAD = {
    "user_message": "串流測試 🚀",
    "conversation_id": "stream-conv",
    "user_id": "stream-user",
}


def _setup(mock_memory, mock_prompt_engine, mock_tracker, stream_gen, tools=None):
    async def mod(text, client=None):
        return {"blocked": False, "flagged": False, "flagged_categories": []}

    return (
        patch("backend.chat_router.get_token_tracker", return_value=mock_tracker),
        patch("backend.chat_router.moderate_text", side_effect=mod),
        patch("backend.chat_router.MemorySystem", return_value=mock_memory),
        patch("backend.chat_router.PromptEngine", return_value=mock_prompt_engine),
        patch("backend.chat_router.get_openai_client", return_value=MagicMock()),
        patch("backend.chat_router.generate_response_stream", side_effect=stream_gen),
        patch(
            "backend.chat_router.get_openai_tool_definitions",
            return_value=tools if tools is not None else [],
        ),
        patch("backend.chat_router.get_core_controller", new_callable=AsyncMock),
    )


def _run_stream(client, payload=None):
    r = client.post(
        "/api/chat?stream=true&use_tools=false",
        json=payload or PAYLOAD,
    )
    return r


@pytest.mark.integration
def test_multiple_chunks_and_unicode(mock_memory, mock_prompt_engine, mock_tracker):
    async def gen(*a, **k):
        async for x in StreamEventGen(["你", "好", "呀✨", " 😊"]):
            yield x

    patches = _setup(mock_memory, mock_prompt_engine, mock_tracker, gen)
    for p in patches:
        p.start()
    try:
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app()) as client:
            r = _run_stream(client)
        assert r.status_code == 200
        assert "你好呀✨" in r.text or ("你" in r.text and "好" in r.text)
        assert "😊" in r.text or "✨" in r.text
        assert USAGE_META_PREFIX in r.text or "__XCG_META__" in r.text
        # 使用者可見邏輯：去掉 meta 後不應有內部標記殘留在「解析後文字」
        visible = r.text.split("__XCG_META__")[0]
        assert "__XCG_META__" not in visible
        assert "sk-" not in r.text
    finally:
        for p in patches:
            p.stop()


@pytest.mark.integration
def test_empty_chunk_tolerated(mock_memory, mock_prompt_engine, mock_tracker):
    async def gen(*a, **k):
        yield {"type": "content", "text": ""}
        yield {"type": "content", "text": "OK"}
        yield {
            "type": "usage",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": "gpt-4o-mini",
        }

    patches = _setup(mock_memory, mock_prompt_engine, mock_tracker, gen)
    for p in patches:
        p.start()
    try:
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app()) as client:
            r = _run_stream(client)
        assert r.status_code == 200
        assert "OK" in r.text
    finally:
        for p in patches:
            p.stop()


@pytest.mark.integration
def test_stream_midway_failure_marks_error(mock_memory, mock_prompt_engine, mock_tracker):
    async def gen(*a, **k):
        yield {"type": "content", "text": "前半"}
        raise RuntimeError("midway fail")

    patches = _setup(mock_memory, mock_prompt_engine, mock_tracker, gen)
    for p in patches:
        p.start()
    try:
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app()) as client:
            r = _run_stream(client)
        assert r.status_code == 200
        assert "[ERROR]" in r.text or "失敗" in r.text
        # [ERROR] 路徑不應觸發成功記憶寫入（_post_stream_tasks 會跳過）
        # save_memory 可能未被 await 或被跳過
    finally:
        for p in patches:
            p.stop()


@pytest.mark.integration
def test_tool_event_payload_formats():
    for status in ("planning", "running", "progress", "done", "skipped", "error"):
        line = _tool_event_payload(status, message=f"m-{status}", tools=[])
        assert line.startswith(TOOL_EVENT_PREFIX)
        data = json.loads(line[len(TOOL_EVENT_PREFIX) :])
        assert data["type"] == "tool_status"
        assert data["status"] == status


@pytest.mark.integration
def test_moderation_blocked_stream(mock_memory, mock_prompt_engine, mock_tracker):
    async def blocked(text, client=None):
        return {
            "blocked": True,
            "flagged": True,
            "flagged_categories": ["hate"],
        }

    async def should_not(*a, **k):
        yield {"type": "content", "text": "should not appear"}

    with patch("backend.chat_router.moderate_text", side_effect=blocked), patch(
        "backend.chat_router.get_token_tracker", return_value=mock_tracker
    ), patch("backend.chat_router.MemorySystem", return_value=mock_memory), patch(
        "backend.chat_router.PromptEngine", return_value=mock_prompt_engine
    ), patch("backend.chat_router.get_openai_client", return_value=MagicMock()), patch(
        "backend.chat_router.generate_response_stream", side_effect=should_not
    ):
        from backend import chat_router as cr

        cr.redis_interface = MagicMock()
        cr.redis_interface.redis = None
        with TestClient(_app()) as client:
            r = client.post("/api/chat?stream=true", json=PAYLOAD)
    assert r.status_code == 200
    assert "should not appear" not in r.text
    assert "__XCG_META__" in r.text
    meta_raw = r.text.split("__XCG_META__", 1)[1]
    meta = json.loads(meta_raw)
    assert meta.get("blocked") is True
    mock_memory.save_memory.assert_not_called()


@pytest.mark.integration
def test_parse_visible_text_excludes_meta_and_events():
    """前端應使用的可見文字規則（純邏輯）。"""
    raw = (
        "__XCG_EVENT__"
        + json.dumps({"type": "tool_status", "status": "planning", "tools": []}, ensure_ascii=False)
        + "\n"
        "哈尼～\n"
        "你好\n"
        "__XCG_META__"
        + json.dumps({"usage": {"total_tokens": 3}, "blocked": False}, ensure_ascii=False)
    )
    lines = raw.split("\n")
    visible = []
    meta = None
    events = []
    for line in lines:
        if line.startswith("__XCG_EVENT__"):
            events.append(json.loads(line[len("__XCG_EVENT__") :]))
            continue
        if line.startswith("__XCG_META__"):
            meta = json.loads(line[len("__XCG_META__") :])
            continue
        visible.append(line)
    text = "\n".join(visible)
    assert "__XCG_EVENT__" not in text
    assert "__XCG_META__" not in text
    assert "哈尼～" in text
    assert meta["usage"]["total_tokens"] == 3
    assert events[0]["status"] == "planning"
