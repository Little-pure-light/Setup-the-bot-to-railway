"""
FineTune Dataset Builder (Infrastructure Phase).

- Export JSONL for later QLoRA / SFT
- Validate dataset rows
- Statistics
- NO model training
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from backend.modules.reflection_contract import normalize_reflection

logger = logging.getLogger("finetune_dataset")


REQUIRED_KEYS = ("messages",)


def _parse_day(ts: str) -> str:
    if not ts:
        return ""
    return str(ts)[:10]


def build_sft_row(
    *,
    user_message: str,
    assistant_message: str,
    system_prompt: str = "",
    reflection: Any = None,
    user_id: str = "",
    conversation_id: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message or ""})
    messages.append({"role": "assistant", "content": assistant_message or ""})
    row: Dict[str, Any] = {
        "messages": messages,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if reflection is not None:
        row["reflection"] = normalize_reflection(reflection)
    if meta:
        row["meta"] = meta
    return row


def validate_row(row: Dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(row, dict):
        return False, "row must be object"
    if "messages" not in row or not isinstance(row["messages"], list):
        return False, "messages required list"
    if len(row["messages"]) < 1:
        return False, "messages empty"
    for m in row["messages"]:
        if not isinstance(m, dict):
            return False, "message must be object"
        if m.get("role") not in ("system", "user", "assistant", "tool"):
            return False, f"invalid role: {m.get('role')}"
        if "content" not in m:
            return False, "message content required"
    return True, "ok"


def validate_dataset(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    ok = 0
    errors: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        total += 1
        good, msg = validate_row(row)
        if good:
            ok += 1
        else:
            errors.append({"index": i, "error": msg})
    return {
        "total": total,
        "valid": ok,
        "invalid": total - ok,
        "errors": errors[:50],
        "ok": total > 0 and ok == total,
    }


def dataset_statistics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    users = set()
    convs = set()
    with_reflection = 0
    roles = {"user": 0, "assistant": 0, "system": 0}
    for r in rows:
        if r.get("user_id"):
            users.add(r["user_id"])
        if r.get("conversation_id"):
            convs.add(r["conversation_id"])
        if r.get("reflection"):
            with_reflection += 1
        for m in r.get("messages") or []:
            role = m.get("role")
            if role in roles:
                roles[role] += 1
    return {
        "rows": len(rows),
        "unique_users": len(users),
        "unique_conversations": len(convs),
        "with_reflection": with_reflection,
        "role_counts": roles,
    }


def filter_records(
    records: List[Dict[str, Any]],
    *,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out = []
    for r in records:
        if user_id and r.get("user_id") != user_id:
            continue
        if conversation_id and r.get("conversation_id") != conversation_id:
            continue
        day = _parse_day(r.get("created_at") or r.get("timestamp") or "")
        if date_from and day and day < date_from[:10]:
            continue
        if date_to and day and day > date_to[:10]:
            continue
        out.append(r)
    return out


def records_from_memory_rows(
    memory_rows: List[Dict[str, Any]],
    *,
    system_prompt: str = "You are 小宸光, a sincere AI companion.",
) -> List[Dict[str, Any]]:
    """Convert V1 conversation table rows into SFT JSONL rows."""
    rows: List[Dict[str, Any]] = []
    for m in memory_rows or []:
        u = m.get("user_message") or ""
        a = m.get("assistant_message") or ""
        if not u and not a:
            continue
        rows.append(
            build_sft_row(
                user_message=u,
                assistant_message=a,
                system_prompt=system_prompt,
                user_id=m.get("user_id") or "",
                conversation_id=m.get("conversation_id") or "",
                meta={"source": "memory_table", "memory_id": m.get("id")},
            )
        )
    return rows


def export_jsonl(
    rows: List[Dict[str, Any]],
    path: Union[str, Path],
    *,
    validate: bool = True,
) -> Dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if validate:
        report = validate_dataset(rows)
        if not report["ok"]:
            return {"ok": False, "path": str(path), "validation": report}
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = dataset_statistics(rows)
    return {"ok": True, "path": str(path), "stats": stats, "count": len(rows)}


def load_jsonl(path: Union[str, Path]) -> List[Dict[str, Any]]:
    path = Path(path)
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("skip bad jsonl line")
    return rows
