"""
OpenAI-compatible API adapter for Open WebUI (and similar clients).

Endpoints:
  GET  /v1/models
  POST /v1/chat/completions

Delegates to existing chat_router.chat() without modifying that pipeline.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("openai_compat")

router = APIRouter(tags=["openai-compat"])

MODEL_ID = "xiaochenguang"
USAGE_META_PREFIX = "\n__XCG_META__"
TOOL_EVENT_PREFIX = "__XCG_EVENT__"

# Headers Open WebUI / proxies may send for stable conversation mapping
_CONV_HEADERS = (
    "x-conversation-id",
    "x-openwebui-chat-id",
    "x-chat-id",
    "x-session-id",
)
_USER_HEADERS = (
    "x-user-id",
    "x-openwebui-user-id",
)


# ---------------------------------------------------------------------------
# Request models (OpenAI Chat Completions subset)
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = "user"
    content: Optional[Union[str, List[Any]]] = None
    name: Optional[str] = None


class OpenAIChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: Optional[str] = MODEL_ID
    messages: List[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    user: Optional[str] = None
    # Optional non-standard fields some clients send
    conversation_id: Optional[str] = None
    chat_id: Optional[str] = None
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    parts.append(str(part["text"]))
                elif "text" in part:
                    parts.append(str(part["text"]))
            else:
                parts.append(str(part))
        return "\n".join(p for p in parts if p)
    return str(content)


def extract_user_message(messages: List[ChatMessage]) -> str:
    """Last user message text; fallback to last non-system message."""
    for msg in reversed(messages or []):
        if (msg.role or "").lower() == "user":
            text = _content_to_text(msg.content).strip()
            if text:
                return text
    for msg in reversed(messages or []):
        if (msg.role or "").lower() != "system":
            text = _content_to_text(msg.content).strip()
            if text:
                return text
    return ""


def resolve_user_id(http_request: Request, body: OpenAIChatCompletionRequest) -> str:
    for h in _USER_HEADERS:
        val = (http_request.headers.get(h) or "").strip()
        if val:
            return val[:200]
    if body.user and str(body.user).strip():
        return str(body.user).strip()[:200]
    return "openwebui_user"


def _stable_id(*parts: str) -> str:
    raw = ":".join(p for p in parts if p)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"owui_{digest}"


def resolve_conversation_id(
    http_request: Request,
    body: OpenAIChatCompletionRequest,
    user_id: str,
) -> str:
    """
    Stable per Open WebUI chat — not per message.

    Priority:
      1. Conversation / chat / session headers
      2. Body conversation_id / chat_id / session_id
      3. Stable hash(user_id + chat_or_session_key)
    """
    for h in _CONV_HEADERS:
        val = (http_request.headers.get(h) or "").strip()
        if val:
            return val[:200]

    for field in (body.conversation_id, body.chat_id, body.session_id):
        if field and str(field).strip():
            return str(field).strip()[:200]

    # Open WebUI may not send chat id; keep one conversation per user as last resort
    # so multi-turn still shares memory instead of new id every message.
    chat_key = (
        (http_request.headers.get("x-openwebui-chat-id") or "").strip()
        or (body.chat_id or body.session_id or body.conversation_id or "default")
    )
    return _stable_id(user_id, str(chat_key))


def _is_internal_marker_line(line: str) -> bool:
    s = line.lstrip("\n")
    return s.startswith(TOOL_EVENT_PREFIX) or s.startswith("__XCG_META__") or s.startswith(
        USAGE_META_PREFIX.strip()
    )


def strip_internal_protocol(text: str) -> str:
    """Remove __XCG_EVENT__ / __XCG_META__ lines and trailing meta blob."""
    if not text:
        return ""
    # Drop meta suffix if glued
    if "__XCG_META__" in text:
        text = text.split("__XCG_META__", 1)[0]
    if USAGE_META_PREFIX in text:
        text = text.split(USAGE_META_PREFIX, 1)[0]
    lines = text.split("\n")
    kept = [ln for ln in lines if not _is_internal_marker_line(ln)]
    return "\n".join(kept).rstrip()


def _openai_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def build_completion_response(
    *,
    content: str,
    model: str = MODEL_ID,
    usage: Optional[Dict[str, Any]] = None,
    finish_reason: str = "stop",
) -> Dict[str, Any]:
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(
        usage.get("total_tokens") or (prompt_tokens + completion_tokens)
    )
    return {
        "id": _openai_completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content or "",
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }


def _sse_chunk(
    *,
    completion_id: str,
    model: str,
    delta: Dict[str, Any],
    finish_reason: Optional[str] = None,
) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _iter_stream_text(response: StreamingResponse) -> AsyncIterator[str]:
    body = response.body_iterator
    async for chunk in body:
        if chunk is None:
            continue
        if isinstance(chunk, bytes):
            yield chunk.decode("utf-8", errors="replace")
        else:
            yield str(chunk)


async def openai_sse_from_xcg_stream(
    response: StreamingResponse,
    *,
    model: str = MODEL_ID,
) -> AsyncIterator[str]:
    """
    Convert XiaoChenGuang plain stream (+ internal markers) to OpenAI SSE.
    """
    completion_id = _openai_completion_id()
    yield _sse_chunk(
        completion_id=completion_id,
        model=model,
        delta={"role": "assistant", "content": ""},
    )

    buffer = ""
    async for piece in _iter_stream_text(response):
        buffer += piece
        # Process complete lines; keep incomplete tail in buffer
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line_full = line  # without newline
            if _is_internal_marker_line(line_full) or line_full.startswith("__XCG_META__"):
                continue
            # Meta may appear mid-line glued after text
            if "__XCG_META__" in line_full:
                line_full = line_full.split("__XCG_META__", 1)[0]
            if not line_full and piece:
                # empty line from split — skip pure empties unless intentional
                continue
            if line_full:
                # re-add newline as content boundary between lines (except first)
                text = line_full
                yield _sse_chunk(
                    completion_id=completion_id,
                    model=model,
                    delta={"content": text + "\n"},
                )

    # Remainder (no trailing newline)
    if buffer:
        if not _is_internal_marker_line(buffer) and not buffer.startswith("__XCG_META__"):
            if "__XCG_META__" in buffer:
                buffer = buffer.split("__XCG_META__", 1)[0]
            if buffer:
                yield _sse_chunk(
                    completion_id=completion_id,
                    model=model,
                    delta={"content": buffer},
                )

    yield _sse_chunk(
        completion_id=completion_id,
        model=model,
        delta={},
        finish_reason="stop",
    )
    yield "data: [DONE]\n\n"


def _usage_from_chat_response(result: Any) -> Dict[str, Any]:
    if result is None:
        return {}
    if hasattr(result, "usage") and isinstance(result.usage, dict):
        return result.usage
    if isinstance(result, dict) and isinstance(result.get("usage"), dict):
        return result["usage"]
    return {}


def _text_from_chat_result(result: Any) -> str:
    if result is None:
        return ""
    # Pydantic ChatResponse
    if hasattr(result, "assistant_message"):
        return strip_internal_protocol(str(result.assistant_message or ""))
    if isinstance(result, dict):
        if "assistant_message" in result:
            return strip_internal_protocol(str(result.get("assistant_message") or ""))
        if "message" in result and isinstance(result["message"], str):
            return strip_internal_protocol(result["message"])
    if isinstance(result, JSONResponse):
        try:
            body = result.body
            if isinstance(body, bytes):
                data = json.loads(body.decode("utf-8"))
            else:
                data = body
            if isinstance(data, dict):
                return strip_internal_protocol(
                    str(
                        data.get("assistant_message")
                        or data.get("message")
                        or data.get("detail")
                        or ""
                    )
                )
        except Exception:
            return ""
    return strip_internal_protocol(str(result))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "xiaochenguang",
            }
        ],
    }


@router.get("/v1/models/{model_id}")
async def get_model(model_id: str):
    if model_id not in (MODEL_ID, "xiaochenguang_v1"):
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "id": MODEL_ID,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "xiaochenguang",
    }


@router.post("/v1/chat/completions")
async def chat_completions(
    body: OpenAIChatCompletionRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
):
    """
    OpenAI Chat Completions → existing POST /api/chat pipeline (via chat()).
    """
    from backend.chat_router import ChatRequest, chat

    user_message = extract_user_message(body.messages)
    if not user_message:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "messages must include a non-empty user message",
                    "type": "invalid_request_error",
                }
            },
        )

    user_id = resolve_user_id(http_request, body)
    conversation_id = resolve_conversation_id(http_request, body, user_id)
    model_name = (body.model or MODEL_ID).strip() or MODEL_ID
    stream = bool(body.stream)

    chat_req = ChatRequest(
        user_message=user_message,
        conversation_id=conversation_id,
        user_id=user_id,
        ai_id="xiaochenguang_v1",
        voice_mode=False,
        car_mode=False,
        input_method="text",
        speak_response=False,
    )

    logger.info(
        "OpenAI-compat chat stream=%s user=%s conv=%s",
        stream,
        user_id[:12],
        conversation_id[:16],
    )

    try:
        result = await chat(
            request=chat_req,
            background_tasks=background_tasks,
            stream=stream,
            use_tools=True,
        )
    except HTTPException as exc:
        # Map to OpenAI-ish error body while keeping status
        detail = exc.detail
        if isinstance(detail, dict):
            message = detail.get("message") or detail.get("error") or str(detail)
        else:
            message = str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": message,
                    "type": "api_error",
                    "code": (
                        detail.get("error")
                        if isinstance(detail, dict)
                        else None
                    ),
                    "param": None,
                }
            },
        )
    except Exception as exc:
        logger.exception("OpenAI-compat chat failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": "Internal server error",
                    "type": "server_error",
                }
            },
        ) from exc

    if stream:
        if isinstance(result, StreamingResponse):
            return StreamingResponse(
                openai_sse_from_xcg_stream(result, model=model_name),
                media_type="text/event-stream; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        # Unexpected non-stream result while stream=true
        text = _text_from_chat_result(result)

        async def one_shot():
            cid = _openai_completion_id()
            yield _sse_chunk(
                completion_id=cid,
                model=model_name,
                delta={"role": "assistant", "content": ""},
            )
            if text:
                yield _sse_chunk(
                    completion_id=cid,
                    model=model_name,
                    delta={"content": text},
                )
            yield _sse_chunk(
                completion_id=cid,
                model=model_name,
                delta={},
                finish_reason="stop",
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            one_shot(),
            media_type="text/event-stream; charset=utf-8",
        )

    # Non-streaming
    if isinstance(result, StreamingResponse):
        # Defensive: consume stream into text
        chunks: List[str] = []
        async for piece in _iter_stream_text(result):
            chunks.append(piece)
        text = strip_internal_protocol("".join(chunks))
        return build_completion_response(content=text, model=model_name)

    if isinstance(result, JSONResponse):
        # moderation blocked etc.
        try:
            raw = result.body
            data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except Exception:
            data = {}
        msg = ""
        if isinstance(data, dict):
            msg = str(
                data.get("message")
                or data.get("assistant_message")
                or data.get("detail")
                or ""
            )
        return JSONResponse(
            status_code=result.status_code,
            content=build_completion_response(
                content=msg or "Request blocked or failed",
                model=model_name,
                finish_reason="stop",
            )
            if result.status_code < 400
            else {
                "error": {
                    "message": msg or "Request failed",
                    "type": "api_error",
                }
            },
        )

    text = _text_from_chat_result(result)
    usage = _usage_from_chat_response(result)
    return build_completion_response(content=text, model=model_name, usage=usage)
