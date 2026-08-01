"""Task 007 — Open WebUI minimal memory-compatibility adapter tests.

Deterministic; no real model / DB / service. Proves the /v1 adapter decides
ephemeral (no persistent recall/tools/save/emotion/reflection) for Open WebUI
auxiliary tasks and for untrusted identity, while keeping normal OpenAI clients
and the Cloudflare path unchanged. Synthetic ids only — no real user/chat id,
API key, Authorization or message content.
"""
from __future__ import annotations

import asyncio
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.chat_router as chat_router
import backend.openai_compat_router as compat
from backend.openai_compat_router import (
    OpenAIChatCompletionRequest,
    ChatMessage,
    resolve_task,
    is_auxiliary_task,
    has_trustworthy_user,
    resolve_user_id,
    resolve_conversation_id,
)


class _FakeHeaders:
    """Case-insensitive header map like starlette's."""
    def __init__(self, data=None):
        self._d = {k.lower(): v for k, v in (data or {}).items()}

    def get(self, k, default=None):
        return self._d.get(k.lower(), default)


class _FakeRequest:
    def __init__(self, headers=None):
        self.headers = _FakeHeaders(headers)


class _FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *a, **k):
        self.tasks.append((fn, a, k))


def _body(user=None, **extra):
    return OpenAIChatCompletionRequest(
        model="xiaochenguang",
        messages=[ChatMessage(role="user", content="嗨")],
        user=user,
        **extra,
    )


def _run(coro):
    # Always create + close a fresh event loop per call so we never depend on a
    # global/leftover loop (an earlier async test in the full suite may have closed
    # the main-thread loop). asyncio.run() is the stable, order-independent choice.
    return asyncio.run(coro)


def _capture_chat(monkeypatch):
    """Patch the chat() the adapter awaits; capture ChatRequest + use_tools."""
    captured = {}

    async def _fake_chat(*, request, background_tasks, stream, use_tools):
        captured["request"] = request
        captured["use_tools"] = use_tools
        return {"assistant_message": "ok"}

    monkeypatch.setattr(chat_router, "chat", AsyncMock(side_effect=_fake_chat))
    return captured


# ---- helper-level ---------------------------------------------------------

def test_is_auxiliary_task_classification():
    for t in ("title_generation", "tags_generation", "query_generation",
              "follow_up_generation", "emoji_generation", "autocomplete_generation"):
        assert is_auxiliary_task(t) is True
    for t in ("", "default", "chat", "user_response"):
        assert is_auxiliary_task(t) is False
    # unknown non-empty task -> fail-closed to auxiliary
    assert is_auxiliary_task("some_future_internal_task") is True


def test_resolve_task_prefers_header_then_body_extra():
    req = _FakeRequest({"X-OpenWebUI-Task": "Title_Generation"})
    assert resolve_task(req, _body()) == "title_generation"
    req2 = _FakeRequest({})
    assert resolve_task(req2, _body(task="tags_generation")) == "tags_generation"
    assert resolve_task(_FakeRequest({}), _body()) == ""


def test_has_trustworthy_user():
    assert has_trustworthy_user(_FakeRequest({"X-OpenWebUI-User-Id": "u1"}), _body()) is True
    assert has_trustworthy_user(_FakeRequest({}), _body(user="u2")) is True
    assert has_trustworthy_user(_FakeRequest({}), _body()) is False


def test_two_users_distinct_owners():
    u1 = resolve_user_id(_FakeRequest({"X-OpenWebUI-User-Id": "alice"}), _body())
    u2 = resolve_user_id(_FakeRequest({"X-OpenWebUI-User-Id": "bob"}), _body())
    assert u1 != u2 and u1 == "alice" and u2 == "bob"


def test_two_chat_ids_distinct_conversations():
    uid = "alice"
    c1 = resolve_conversation_id(_FakeRequest({"X-OpenWebUI-Chat-Id": "chatA"}), _body(), uid)
    c2 = resolve_conversation_id(_FakeRequest({"X-OpenWebUI-Chat-Id": "chatB"}), _body(), uid)
    assert c1 != c2


# ---- adapter decision (captures the ChatRequest passed to chat()) ---------

def test_auxiliary_task_is_ephemeral_and_tools_off(monkeypatch):
    cap = _capture_chat(monkeypatch)
    req = _FakeRequest({"X-OpenWebUI-User-Id": "alice", "X-OpenWebUI-Task": "title_generation"})
    _run(compat.chat_completions(body=_body(user="alice"), http_request=req,
                                 background_tasks=_FakeBackgroundTasks()))
    assert cap["request"].suppress_memory is True   # no persistent recall/save/emotion/reflection
    assert cap["use_tools"] is False                # tools off for aux tasks


def test_missing_identity_fail_closed_non_persistent(monkeypatch):
    cap = _capture_chat(monkeypatch)
    req = _FakeRequest({})  # no user headers, no body.user
    _run(compat.chat_completions(body=_body(user=None), http_request=req,
                                 background_tasks=_FakeBackgroundTasks()))
    r = cap["request"]
    assert r.suppress_memory is True                       # allowed to reply, but ephemeral
    assert r.user_id.startswith("owui_ephemeral_")         # per-request, not shared bucket
    assert r.user_id != "openwebui_user"                   # not the old shared fallback
    assert r.conversation_id.startswith("owui_ephemeral_")
    # never derived from message content / auth
    assert "嗨" not in r.user_id and "嗨" not in r.conversation_id


def test_normal_no_task_request_unchanged(monkeypatch):
    cap = _capture_chat(monkeypatch)
    req = _FakeRequest({"X-OpenWebUI-User-Id": "alice", "X-OpenWebUI-Chat-Id": "chatA"})
    _run(compat.chat_completions(body=_body(user="alice"), http_request=req,
                                 background_tasks=_FakeBackgroundTasks()))
    r = cap["request"]
    assert r.suppress_memory is False   # normal persistent path
    assert cap["use_tools"] is True
    assert r.user_id == "alice"
    assert r.ai_id == "xiaochenguang_v1"  # Task006 isolation key preserved


def test_trusted_user_but_aux_task_still_ephemeral(monkeypatch):
    cap = _capture_chat(monkeypatch)
    req = _FakeRequest({"X-OpenWebUI-User-Id": "alice", "X-OpenWebUI-Task": "tags_generation"})
    _run(compat.chat_completions(body=_body(user="alice"), http_request=req,
                                 background_tasks=_FakeBackgroundTasks()))
    assert cap["request"].suppress_memory is True
    assert cap["use_tools"] is False


# ---- chat_router flag contract (Cloudflare regression) --------------------

def test_chatrequest_default_suppress_memory_is_false():
    """Default False => Cloudflare and all existing callers keep persistent memory."""
    req = chat_router.ChatRequest(user_message="hi", conversation_id="c", user_id="u")
    assert req.suppress_memory is False
    req2 = chat_router.ChatRequest(user_message="hi", conversation_id="c", user_id="u",
                                   suppress_memory=True)
    assert req2.suppress_memory is True


# ===========================================================================
# Real chat_router.chat() control-flow side-effect regression (Codex必修2).
# These do NOT mock chat() — they run the actual chat() and count how many times
# recall / history / save / post-chat / Kernel are invoked. Everything below the
# entry (LLM, moderation, usage, redis) is stubbed with synthetic no-ops so the
# real control flow (kernel gate + suppress_memory gates) executes deterministically.
# ===========================================================================

class _FakeStreamingResponse:
    """Captures the async body generator so the test can drain it."""
    def __init__(self, body_iterator, *a, **k):
        self.body_iterator = body_iterator


def _spy_memory_system():
    ms = types.SimpleNamespace()
    ms.recall_memories = AsyncMock(return_value="")
    ms.get_conversation_history = MagicMock(return_value=[])
    ms.save_memory = AsyncMock(return_value=None)
    return ms


def _patch_chat_env(mp, *, kernel_returns=None):
    """Patch chat_router module deps so the REAL chat() runs without services.
    Returns (memory_system_spy, kernel_spy, post_chat_spy, background_tasks_fake)."""
    ms = _spy_memory_system()
    kernel_spy = AsyncMock(return_value=kernel_returns)      # None => fall through to Legacy
    post_chat_spy = AsyncMock(return_value=None)

    class _FakeBG:
        def __init__(self): self.added = []
        def add_task(self, fn, *a, **k): self.added.append((fn, a, k))
    bg = _FakeBG()

    tracker = types.SimpleNamespace(
        check_budget=lambda uid: (True, "", {}),
        get_user_daily_summary=lambda uid: {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "cost_usd": 0, "budget_usd": 0, "remaining_usd": 0, "calls": 0},
    )

    class _FakePromptEngine:
        def __init__(self, *a, **k): pass
        async def build_prompt(self, *a, **k):
            return ([{"role": "system", "content": "sys"},
                     {"role": "user", "content": "hi"}], {"primary_emotion": "neutral"})

    async def _fake_stream(*a, **k):
        yield {"type": "content", "text": "hi"}
        yield {"type": "usage", "usage": {"total_tokens": 1, "prompt_tokens": 1,
                                          "completion_tokens": 0}}

    mp.setattr(chat_router, "_try_kernel_chat", kernel_spy)
    mp.setattr(chat_router, "run_post_chat_tasks", post_chat_spy)
    mp.setattr(chat_router, "_build_memory_system", lambda *a, **k: ms)
    mp.setattr(chat_router, "PromptEngine", _FakePromptEngine)
    mp.setattr(chat_router, "get_openai_client", lambda *a, **k: object())
    mp.setattr(chat_router, "get_token_tracker", lambda *a, **k: tracker)
    mp.setattr(chat_router, "moderate_text", AsyncMock(return_value={"blocked": False}))
    mp.setattr(chat_router, "get_tool_registry", lambda *a, **k: object())
    mp.setattr(chat_router, "get_openai_tool_definitions", lambda *a, **k: [])
    mp.setattr(chat_router, "generate_response",
               AsyncMock(return_value={"content": "hi", "usage": {"total_tokens": 1}}))
    mp.setattr(chat_router, "generate_response_with_tools",
               AsyncMock(return_value={"content": "hi", "finish_reason": "stop",
                                       "tool_calls": [], "usage": {"total_tokens": 1}}))
    mp.setattr(chat_router, "generate_response_stream", _fake_stream)
    mp.setattr(chat_router, "_merge_usage", lambda *a, **k: {
        "total_tokens": 1, "prompt_tokens": 1, "completion_tokens": 0, "cost_usd": 0})
    mp.setattr(chat_router, "_record_usage", lambda *a, **k: {"daily": {}})
    mp.setattr(chat_router, "redis_interface", types.SimpleNamespace(redis=None))
    mp.setattr(chat_router, "StreamingResponse", _FakeStreamingResponse)
    return ms, kernel_spy, post_chat_spy, bg


def _ephemeral_req():
    return chat_router.ChatRequest(
        user_message="hi", conversation_id="owui_ephemeral_x",
        user_id="owui_ephemeral_x", suppress_memory=True)


def _normal_req():
    return chat_router.ChatRequest(
        user_message="hi", conversation_id="c-1", user_id="alice",
        suppress_memory=False)


def test_realflow_kernel_bypassed_and_nonstream_zero_side_effects(monkeypatch):
    """suppress_memory=True (non-stream): Kernel not entered; recall/history/save/
    post-chat all 0 — proven against the real chat() control flow."""
    ms, kernel_spy, post_chat_spy, bg = _patch_chat_env(monkeypatch)
    _run(chat_router.chat(request=_ephemeral_req(), background_tasks=bg,
                          stream=False, use_tools=False, include_reflection=False))
    assert kernel_spy.await_count == 0            # Kernel bypassed entirely
    assert ms.recall_memories.await_count == 0
    assert ms.get_conversation_history.call_count == 0
    assert ms.save_memory.await_count == 0
    assert post_chat_spy.await_count == 0
    assert bg.added == []                          # run_post_chat_tasks not scheduled


def test_realflow_legacy_ephemeral_stream_zero_side_effects(monkeypatch):
    """suppress_memory=True (stream): after the stream completes, the post-stream
    save + post-chat tasks run 0 times — proven by draining the real generator."""
    ms, kernel_spy, post_chat_spy, bg = _patch_chat_env(monkeypatch)
    resp = _run(chat_router.chat(request=_ephemeral_req(), background_tasks=bg,
                                 stream=True, use_tools=False, include_reflection=False))

    async def _drain_and_settle():
        async for _ in resp.body_iterator:
            pass
        await asyncio.sleep(0.05)   # let the scheduled _post_stream_tasks run
    _run(_drain_and_settle())

    assert kernel_spy.await_count == 0
    assert ms.save_memory.await_count == 0
    assert post_chat_spy.await_count == 0


def test_realflow_normal_path_enters_kernel_and_persists(monkeypatch):
    """suppress_memory=False (non-stream): Kernel is consulted and the original
    Legacy flow runs — recall + save happen, post-chat is scheduled."""
    ms, kernel_spy, post_chat_spy, bg = _patch_chat_env(monkeypatch, kernel_returns=None)
    _run(chat_router.chat(request=_normal_req(), background_tasks=bg,
                          stream=False, use_tools=False, include_reflection=False))
    assert kernel_spy.await_count == 1            # Kernel consulted (returned None -> Legacy)
    assert ms.recall_memories.await_count == 1    # original recall ran
    assert ms.get_conversation_history.call_count == 1
    assert ms.save_memory.await_count == 1        # persistent save ran
    assert any(a[0] is chat_router.run_post_chat_tasks for a in bg.added)
