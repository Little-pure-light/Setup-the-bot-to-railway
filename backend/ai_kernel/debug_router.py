"""
Debug Trace API — 嚴格鎖定。

必須同時滿足：
1. KERNEL_DEBUG_ENABLED=true
2. 有效 Bearer：KERNEL_DEBUG_SECRET 或 API_SECRET（至少一個必須已設定）
3. 生產環境（RAILWAY_ENVIRONMENT / ENV=production）若無 secret → 永遠 404

不回傳完整 prompt / 記憶 / secret。
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.ai_kernel.feature_flags import get_kernel_flags
from backend.ai_kernel.tracing import get_trace, list_recent_traces

router = APIRouter()


def _is_production() -> bool:
    env = (
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("ENV")
        or os.getenv("ENVIRONMENT")
        or ""
    ).strip().lower()
    return env in ("production", "prod", "live")


def _debug_secret() -> str:
    return (
        os.getenv("KERNEL_DEBUG_SECRET")
        or os.getenv("API_SECRET")
        or ""
    ).strip()


def _auth(authorization: Optional[str]) -> None:
    flags = get_kernel_flags()
    if not flags.debug_enabled:
        raise HTTPException(status_code=404, detail="Not Found")

    secret = _debug_secret()
    if not secret:
        # 無 secret 時：生產一律關閉；開發也不開列表（避免誤曝）
        raise HTTPException(status_code=404, detail="Not Found")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1].strip()
    if token != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/kernel/debug/traces")
async def debug_list_traces(
    authorization: Optional[str] = Header(default=None),
    limit: int = 20,
):
    _auth(authorization)
    # 僅摘要，不附 spans 全文可選 — 仍只含 stage 指標
    traces = list_recent_traces(limit=min(max(limit, 1), 20))
    return {"traces": traces, "count": len(traces)}


@router.get("/kernel/debug/traces/{trace_id}")
async def debug_get_trace(
    trace_id: str,
    authorization: Optional[str] = Header(default=None),
):
    _auth(authorization)
    # 防止 path 注入超長 id
    tid = (trace_id or "").strip()[:32]
    if not tid.isalnum():
        raise HTTPException(status_code=400, detail="invalid trace_id")
    data = get_trace(tid)
    if not data:
        raise HTTPException(status_code=404, detail="Not Found")
    return data
