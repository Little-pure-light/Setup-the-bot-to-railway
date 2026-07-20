"""
提醒工具（本機 / Redis 持久化）

支援：新增、列出、刪除提醒。供對話中設定待辦與時間提醒。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tools.reminder")

_lock = threading.RLock()
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "reminders.json"


def _path() -> Path:
    return Path(os.getenv("REMINDERS_FILE", str(_DEFAULT_PATH)))


def _load() -> List[Dict[str, Any]]:
    p = _path()
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"⚠️ 讀取提醒失敗: {e}")
        return []


def _save(items: List[Dict[str, Any]]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _parse_when(when: str) -> Optional[str]:
    """
    解析相對或簡易時間，回傳 ISO 字串（UTC+8 標註為文字）。
    支援：30m / 2h / 1d / YYYY-MM-DD HH:MM / 明天 等簡寫。
    """
    raw = (when or "").strip()
    if not raw:
        return None
    now = datetime.now()
    lower = raw.lower()

    try:
        if lower.endswith("m") and lower[:-1].isdigit():
            dt = now + timedelta(minutes=int(lower[:-1]))
            return dt.strftime("%Y-%m-%d %H:%M")
        if lower.endswith("h") and lower[:-1].isdigit():
            dt = now + timedelta(hours=int(lower[:-1]))
            return dt.strftime("%Y-%m-%d %H:%M")
        if lower.endswith("d") and lower[:-1].isdigit():
            dt = now + timedelta(days=int(lower[:-1]))
            return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass

    if "明天" in raw or lower in ("tomorrow",):
        dt = now + timedelta(days=1)
        # 若有 HH:MM
        import re

        m = re.search(r"(\d{1,2}):(\d{2})", raw)
        if m:
            dt = dt.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0)
        else:
            dt = dt.replace(hour=9, minute=0, second=0)
        return dt.strftime("%Y-%m-%d %H:%M")

    # 直接當字串保存（AI 給的自然語言時間）
    if len(raw) <= 80:
        return raw
    return raw[:80]


async def manage_reminder(
    action: str,
    text: str = "",
    when: str = "",
    reminder_id: str = "",
    user_id: str = "default_user",
) -> str:
    """
    action: set | list | delete
    """
    act = (action or "list").strip().lower()
    uid = (user_id or "default_user").strip() or "default_user"

    with _lock:
        items = _load()

        if act in ("set", "add", "create"):
            body = (text or "").strip()
            if not body:
                return "[REMINDER_ERROR] 請提供提醒內容 text"
            when_label = _parse_when(when) or "未指定時間"
            rid = str(uuid.uuid4())[:8]
            row = {
                "id": rid,
                "user_id": uid,
                "text": body[:200],
                "when": when_label,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "done": False,
            }
            items.append(row)
            # 每使用者最多 50 筆
            user_items = [x for x in items if x.get("user_id") == uid]
            if len(user_items) > 50:
                # 刪最舊
                oldest = sorted(user_items, key=lambda x: x.get("created_at") or "")[
                    : len(user_items) - 50
                ]
                drop_ids = {x["id"] for x in oldest}
                items = [x for x in items if x.get("id") not in drop_ids]
            _save(items)
            return f"✅ 已設定提醒 [{rid}]：{body}（時間：{when_label}）"

        if act in ("list", "ls", "show"):
            mine = [x for x in items if x.get("user_id") == uid and not x.get("done")]
            if not mine:
                return "目前沒有未完成的提醒。"
            lines = ["📋 你的提醒："]
            for x in mine[-20:]:
                lines.append(f"  · [{x.get('id')}] {x.get('when')} — {x.get('text')}")
            return "\n".join(lines)

        if act in ("delete", "remove", "done"):
            rid = (reminder_id or "").strip()
            if not rid and text:
                rid = text.strip()
            if not rid:
                return "[REMINDER_ERROR] 請提供 reminder_id"
            before = len(items)
            items = [
                x
                for x in items
                if not (x.get("user_id") == uid and x.get("id") == rid)
            ]
            if len(items) == before:
                return f"[REMINDER_EMPTY] 找不到提醒 {rid}"
            _save(items)
            return f"🗑️ 已刪除提醒 [{rid}]"

        return f"[REMINDER_ERROR] 不支援的 action：{action}（請用 set/list/delete）"
