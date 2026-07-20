"""
安全日誌與 Request ID 工具（P1-14）

- 不記錄完整私人對話
- 不記錄 Secret / JWT / API Key
- user_id / conversation_id 僅記錄前綴
"""
from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar
from typing import Any, Optional

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{10,}", re.I),
    re.compile(r"eyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),  # JWT-ish
    re.compile(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*\S+"),
]


class ErrorCode:
    AUTH_ERROR = "AUTH_ERROR"
    OPENAI_ERROR = "OPENAI_ERROR"
    OPENAI_TIMEOUT = "OPENAI_TIMEOUT"
    SUPABASE_ERROR = "SUPABASE_ERROR"
    REDIS_ERROR = "REDIS_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    STREAM_ERROR = "STREAM_ERROR"
    UPLOAD_ERROR = "UPLOAD_ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    BUDGET_ERROR = "BUDGET_ERROR"
    MODERATION_BLOCK = "MODERATION_BLOCK"
    UNKNOWN = "UNKNOWN"


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    return rid


def get_request_id() -> str:
    return request_id_var.get() or ""


def short_id(value: Optional[str], n: int = 8) -> str:
    if not value:
        return "-"
    s = str(value)
    return s[:n] + ("…" if len(s) > n else "")


def redact_secrets(text: str) -> str:
    if not text:
        return text
    out = str(text)
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def safe_log_extra(
    *,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    event: str = "",
    duration_ms: Optional[int] = None,
    error_code: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    data = {
        "request_id": get_request_id() or "-",
        "conversation_id": short_id(conversation_id),
        "user_id": short_id(user_id),
        "event": event,
    }
    if duration_ms is not None:
        data["duration_ms"] = duration_ms
    if error_code:
        data["error_code"] = error_code
    for k, v in kwargs.items():
        if k.lower() in ("password", "token", "authorization", "api_key", "message", "content"):
            continue
        data[k] = v
    return data


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact_secrets(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: redact_secrets(str(v)) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact_secrets(a) if isinstance(a, str) else a for a in record.args
                    )
        except Exception:
            pass
        return True


def install_redacting_filter(logger: Optional[logging.Logger] = None) -> None:
    target = logger or logging.getLogger()
    f = RedactingFilter()
    target.addFilter(f)
    for h in target.handlers:
        h.addFilter(f)
