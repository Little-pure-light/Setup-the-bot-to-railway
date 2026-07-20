"""Debug Trace — 只記 stage / 時間 / 數量 / 狀態，不記完整 prompt 或記憶。"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceSpan:
    stage: str
    status: str = "ok"
    duration_ms: int = 0
    counts: Dict[str, int] = field(default_factory=dict)
    error_code: Optional[str] = None


class KernelTrace:
    def __init__(self, request_id: str = "", enabled: bool = False):
        self.trace_id = uuid.uuid4().hex[:12]
        self.request_id = (request_id or "")[:16]
        self.enabled = enabled
        self.spans: List[TraceSpan] = []
        self._starts: Dict[str, float] = {}

    def start(self, stage: str) -> None:
        self._starts[stage] = time.perf_counter()

    def end(
        self,
        stage: str,
        *,
        status: str = "ok",
        counts: Optional[Dict[str, int]] = None,
        error_code: Optional[str] = None,
    ) -> None:
        started = self._starts.pop(stage, None)
        ms = int((time.perf_counter() - started) * 1000) if started else 0
        if not self.enabled:
            return
        self.spans.append(
            TraceSpan(
                stage=stage,
                status=status,
                duration_ms=ms,
                counts=dict(counts or {}),
                error_code=error_code,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "spans": [
                {
                    "stage": s.stage,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "counts": s.counts,
                    "error_code": s.error_code,
                }
                for s in self.spans
            ],
        }


# 進程內 debug 存儲（需 flag；無 secret）
_TRACE_STORE: Dict[str, Dict[str, Any]] = {}


def store_trace(trace: KernelTrace) -> None:
    if not trace.enabled:
        return
    _TRACE_STORE[trace.trace_id] = trace.to_dict()
    # 只保留最近 200 筆
    if len(_TRACE_STORE) > 200:
        for k in list(_TRACE_STORE.keys())[:50]:
            _TRACE_STORE.pop(k, None)


def get_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    return _TRACE_STORE.get(trace_id)


def list_recent_traces(limit: int = 20) -> List[Dict[str, Any]]:
    items = list(_TRACE_STORE.values())[-limit:]
    return list(reversed(items))
