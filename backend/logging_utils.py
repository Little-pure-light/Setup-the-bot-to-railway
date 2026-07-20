"""
安全日誌與 Request ID 工具（P1-14）

- 不記錄完整私人對話
- 不記錄 Secret / JWT / API Key
- user_id / conversation_id 僅記錄前綴

## RedactingFilter 限制（重要）

`RedactingFilter` 只處理 `LogRecord.msg` 與 `record.args` 中的字串。

它 **不保證** 清除：
- `exc_info` / `logger.exception()` 產生的 traceback 文字
- 已格式化進 handler 的完整 exception chain
- 第三方 SDK 自行 print 的輸出

因此：
1. Production 記錄外部 API 失敗時，請使用 `format_external_error()` /
   `log_external_failure()`，避免 `logger.exception(e)` 直接帶入可能含 Secret 的訊息。
2. 仍保留錯誤 **類型**、可選 **error_code**、**request_id**，以利診斷。
3. 本機除錯可設 `LOG_VERBOSE_EXCEPTIONS=true` 輸出脫敏後的短訊息（仍非完整 traceback）。
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from contextvars import ContextVar
from typing import Any, Optional

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{10,}", re.I),
    re.compile(r"eyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),  # JWT-ish
    re.compile(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
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


def format_external_error(
    exc: BaseException,
    *,
    code: str = ErrorCode.UNKNOWN,
    max_len: int = 200,
) -> str:
    """
    將外部 API / SDK 例外轉成可記錄字串。
    Production：只保留 exception 類型 + code + request_id（不附完整 str(exc)）。
    詳細模式：附脫敏後的短訊息，仍不輸出完整 traceback。
    """
    etype = type(exc).__name__
    rid = get_request_id() or "-"
    verbose = os.getenv("LOG_VERBOSE_EXCEPTIONS", "").lower() in ("1", "true", "yes")
    if verbose:
        detail = redact_secrets(str(exc))[:max_len]
        return f"{code} type={etype} request_id={rid} detail={detail}"
    return f"{code} type={etype} request_id={rid}"


def log_external_failure(
    logger: logging.Logger,
    exc: BaseException,
    *,
    code: str = ErrorCode.UNKNOWN,
    event: str = "external_error",
) -> str:
    """
    記錄外部失敗：不使用 logger.exception，避免 traceback 含 Secret。
    回傳已寫入的摘要字串（供測試斷言）。
    """
    summary = format_external_error(exc, code=code)
    logger.error(
        "%s event=%s",
        summary,
        event,
        extra=safe_log_extra(event=event, error_code=code),
    )
    return summary


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
    """
    脫敏 filter。

    限制：不處理 exc_info traceback。見模組 docstring。
    """

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
