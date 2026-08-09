"""
Internal Night Growth trigger endpoint.

POST /internal/night-growth/run
Protected by NIGHT_GROWTH_INTERNAL_TOKEN (or API_SECRET fallback).
Not for public anonymous use.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("internal.night_growth")

router = APIRouter(tags=["internal-night-growth"])


class NightGrowthRunRequest(BaseModel):
    user_id: str = Field(default="default_user", description="Target user id")
    conversation_id: Optional[str] = None
    dry_run: bool = False
    force: bool = False


def _live_runs_enabled() -> bool:
    return os.getenv("NIGHT_GROWTH_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _check_internal_token(authorization: Optional[str], x_internal_token: Optional[str]) -> None:
    expected = (
        os.getenv("NIGHT_GROWTH_INTERNAL_TOKEN")
        or os.getenv("API_SECRET")
        or ""
    ).strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Night growth internal token not configured",
        )
    token = ""
    if x_internal_token:
        token = x_internal_token.strip()
    elif authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        else:
            token = auth
    # 常數時間比對（expected 已於上方保證非空；token/secret 值不記錄、不回顯）。
    if not token or not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _build_manager():
    from backend.modules.memory_manager import MemoryManager
    from modules.memory_system import MemorySystem
    from backend.supabase_handler import get_supabase
    from backend.openai_handler import get_openai_client

    supabase = get_supabase()
    openai_client = get_openai_client()
    table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    redis = None
    try:
        from backend.redis_interface import get_shared_redis_interface

        redis = get_shared_redis_interface()
    except Exception:
        redis = None
    v1 = MemorySystem(supabase, openai_client, table, redis_interface=redis)
    return MemoryManager(v1)


@router.post("/internal/night-growth/run")
async def run_night_growth(
    body: NightGrowthRunRequest,
    authorization: Optional[str] = Header(default=None),
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
) -> Dict[str, Any]:
    """
    Trigger Night Growth once for a user.
    Requires NIGHT_GROWTH_INTERNAL_TOKEN (Bearer or X-Internal-Token).
    """
    _check_internal_token(authorization, x_internal_token)

    # Optional hard disable
    if os.getenv("NIGHT_GROWTH_ENDPOINT_ENABLED", "true").lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        raise HTTPException(status_code=403, detail="Night growth endpoint disabled")

    # Gate 1 safety: authenticated dry-runs stay available, but a real run needs
    # the independent server-side activation flag. The default remains off.
    if not body.dry_run and not _live_runs_enabled():
        raise HTTPException(status_code=403, detail="Night growth live runs disabled")

    try:
        from backend.modules.night_growth import NightGrowth

        manager = _build_manager()
        ng = NightGrowth(manager)
        report = await ng.run_once(
            user_id=body.user_id,
            conversation_id=body.conversation_id,
            dry_run=body.dry_run,
            force=body.force,
        )
        # redact nothing critical; user_id kept for ops but short
        return {
            "ok": report.get("status")
            in ("completed", "completed_dry_run", "skipped_duplicate"),
            "execution_id": report.get("execution_id"),
            "status": report.get("status"),
            "day": report.get("day"),
            "dry_run": report.get("dry_run"),
            "force": report.get("force"),
            "steps": report.get("steps"),
            "saved_ids_count": len(report.get("saved_ids") or []),
            "archived_ids_count": len(report.get("archived_ids") or []),
            "identity_version_id": report.get("identity_version_id"),
            "graph_edge_ids": report.get("graph_edge_ids"),
            "usage": report.get("usage"),
            "error": report.get("error"),
            "message": report.get("message"),
            "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("night growth endpoint failed: %s", e)
        raise HTTPException(status_code=500, detail="night_growth_failed")
