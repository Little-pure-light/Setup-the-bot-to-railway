"""
Night Growth execution safety: lock, idempotency, execution records.

Same user_id + calendar day must not run twice unless force=True.
Failed runs are retriable (failed status releases logical day lock).
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("memory.night_growth_safety")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _safe(uid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in (uid or "default"))[:80]


class NightGrowthExecutionStore:
    """Filesystem-backed execution records + locks (works without Redis migration)."""

    def __init__(self, base_dir: Optional[str] = None):
        root = Path(
            base_dir
            or os.getenv("NIGHT_GROWTH_STORE_DIR")
            or (Path(__file__).resolve().parents[2] / "data" / "night_growth")
        )
        self.base_dir = Path(root)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: str) -> Path:
        d = self.base_dir / _safe(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def idempotency_key(self, user_id: str, day: Optional[str] = None) -> str:
        return f"ng:{_safe(user_id)}:{day or _utc_date()}"

    def _lock_path(self, user_id: str) -> Path:
        return self._user_dir(user_id) / "run.lock"

    def _day_record_path(self, user_id: str, day: str) -> Path:
        return self._user_dir(user_id) / f"day_{day}.json"

    def _exec_path(self, user_id: str, execution_id: str) -> Path:
        return self._user_dir(user_id) / f"exec_{execution_id}.json"

    def acquire_lock(self, user_id: str, *, ttl_seconds: float = 900.0) -> bool:
        lp = self._lock_path(user_id)
        now = time.time()
        if lp.exists():
            try:
                meta = json.loads(lp.read_text(encoding="utf-8"))
                if now - float(meta.get("ts") or 0) < ttl_seconds:
                    return False
            except Exception:
                # stale/corrupt lock → take over
                pass
        lp.write_text(
            json.dumps({"ts": now, "holder": os.getpid(), "at": _iso_now()}),
            encoding="utf-8",
        )
        return True

    def release_lock(self, user_id: str) -> None:
        lp = self._lock_path(user_id)
        try:
            if lp.exists():
                lp.unlink()
        except Exception as e:
            logger.warning("release lock failed: %s", e)

    def get_day_record(self, user_id: str, day: Optional[str] = None) -> Optional[Dict[str, Any]]:
        day = day or _utc_date()
        p = self._day_record_path(user_id, day)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def is_day_completed(self, user_id: str, day: Optional[str] = None) -> bool:
        """True only for formal (non-dry) successful completion."""
        rec = self.get_day_record(user_id, day)
        if not rec:
            return False
        return rec.get("status") == "completed" and not rec.get("dry_run")

    def write_execution(self, record: Dict[str, Any]) -> Path:
        user_id = record.get("user_id") or "default_user"
        eid = record.get("execution_id") or "unknown"
        path = self._exec_path(user_id, eid)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        day = record.get("day") or _utc_date()
        # Day marker: formal completed blocks re-run; dry_run never blocks.
        if record.get("status") in ("completed", "skipped_duplicate", "running", "failed"):
            day_path = self._day_record_path(user_id, day)
            # Do not overwrite a formal completed day with a dry_run record
            prev = None
            if day_path.exists():
                try:
                    prev = json.loads(day_path.read_text(encoding="utf-8"))
                except Exception:
                    prev = None
            if (
                prev
                and prev.get("status") == "completed"
                and not prev.get("dry_run")
                and record.get("dry_run")
            ):
                return path
            day_path.write_text(
                json.dumps(
                    {
                        "day": day,
                        "user_id": user_id,
                        "execution_id": eid,
                        "status": record.get("status"),
                        "dry_run": bool(record.get("dry_run")),
                        "idempotency_key": record.get("idempotency_key"),
                        "updated_at": _iso_now(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return path

    def load_execution(self, user_id: str, execution_id: str) -> Optional[Dict[str, Any]]:
        p = self._exec_path(user_id, execution_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None


def new_step(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "started_at": _iso_now(),
        "completed_at": None,
        "status": "running",
        "error": None,
        "saved_memory_ids": [],
        "identity_version_id": None,
        "graph_edge_ids": [],
    }


def finish_step(
    step: Dict[str, Any],
    *,
    status: str = "ok",
    error: Optional[str] = None,
    saved_memory_ids: Optional[List[Any]] = None,
    identity_version_id: Optional[str] = None,
    graph_edge_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    step["completed_at"] = _iso_now()
    step["status"] = status
    step["error"] = error
    if saved_memory_ids is not None:
        step["saved_memory_ids"] = list(saved_memory_ids)
    if identity_version_id is not None:
        step["identity_version_id"] = identity_version_id
    if graph_edge_ids is not None:
        step["graph_edge_ids"] = list(graph_edge_ids)
    return step
