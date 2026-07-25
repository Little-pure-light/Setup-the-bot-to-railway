"""
Chat pipeline stage timing (Phase 2 observability).

Env:
  REQUEST_TIMING_ENABLED=true|false  (default true)
  Does not change model answer logic.
  Logs only stage names, ms, request_id — never full user text or secrets.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

logger = logging.getLogger("request_timing")


def timing_enabled() -> bool:
    return os.getenv("REQUEST_TIMING_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


class RequestTimer:
    def __init__(self, request_id: str = "", *, conversation_id: str = ""):
        self.request_id = (request_id or "")[:32]
        self.conversation_id = (conversation_id or "")[:16]
        self.stages: List[Dict[str, Any]] = []
        self._t0 = time.perf_counter()
        self.first_token_ms: Optional[int] = None
        self.complete_ms: Optional[int] = None

    @contextmanager
    def stage(self, name: str):
        if not timing_enabled():
            yield
            return
        start = time.perf_counter()
        err = None
        try:
            yield
        except Exception as e:
            err = type(e).__name__
            raise
        finally:
            ms = int((time.perf_counter() - start) * 1000)
            self.stages.append(
                {"stage": name, "ms": ms, "error_type": err or ""}
            )

    def mark_first_token(self):
        """Record TTFB once — only for first displayable assistant text."""
        if self.first_token_ms is None:
            self.first_token_ms = int((time.perf_counter() - self._t0) * 1000)
            return True
        return False

    def note_displayable_text(self, text: Optional[str], *, tool_prefix: str = "", meta_prefix: str = "") -> bool:
        """
        If text is first displayable answer content, mark first token.
        Tool status / empty / usage metadata do not count.
        Returns True if this call set first_token_ms.
        """
        if self.first_token_ms is not None:
            return False
        if text is None:
            return False
        s = str(text)
        if not s.strip():
            return False
        if tool_prefix and s.startswith(tool_prefix):
            return False
        if meta_prefix and s.startswith(meta_prefix):
            return False
        # pure JSON tool event lines sometimes without going through prefix helper
        if s.lstrip().startswith("{") and '"type"' in s and "tool" in s.lower():
            return False
        return bool(self.mark_first_token())

    def mark_complete(self):
        self.complete_ms = int((time.perf_counter() - self._t0) * 1000)

    def record_stage(self, name: str, ms: int, *, error_type: str = ""):
        if not timing_enabled():
            return
        self.stages.append(
            {"stage": name, "ms": int(ms), "error_type": error_type or ""}
        )

    def total_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "conversation_id": self.conversation_id,
            "stages": list(self.stages),
            "first_token_ms": self.first_token_ms,
            "complete_ms": self.complete_ms if self.complete_ms is not None else self.total_ms(),
            "total_ms": self.total_ms(),
        }

    def log_summary(self):
        if not timing_enabled():
            return
        d = self.as_dict()
        parts = [f"{s['stage']}={s['ms']}ms" for s in d["stages"]]
        logger.info(
            "chat_timing request_id=%s conv=%s total_ms=%s first_token_ms=%s %s",
            d["request_id"],
            d["conversation_id"],
            d["total_ms"],
            d["first_token_ms"],
            " ".join(parts),
        )
        print(
            f"⏱ chat_timing rid={d['request_id'][:8]}… total={d['total_ms']}ms "
            f"ttfb={d['first_token_ms']} "
            + " ".join(parts)
        )
