"""Debug Trace API — 需 KERNEL_DEBUG_ENABLED 與授權。"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.ai_kernel.feature_flags import get_kernel_flags
from backend.ai_kernel.tracing import get_trace, list_recent_traces

router = APIRouter()


def _auth(authorization: Optional[str]) -> None:
    flags = get_kernel_flags()
    if not flags.debug_enabled:
        raise HTTPException(status_code=404, detail="debug disabled")
    secret = os.getenv("API_SECRET", "")
    if not secret:
        # 無 API_SECRET 時仍要求 flag，但允許本機
        return
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
    return {"traces": list_recent_traces(limit=min(limit, 50))}


@router.get("/kernel/debug/traces/{trace_id}")
async def debug_get_trace(
    trace_id: str,
    authorization: Optional[str] = Header(default=None),
):
    _auth(authorization)
    data = get_trace(trace_id)
    if not data:
        raise HTTPException(status_code=404, detail="not found")
    return data
