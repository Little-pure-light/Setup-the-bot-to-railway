"""
Unified Reflection Contract (Infrastructure Phase).

All modules (ReflectionStorage, Memory, API) MUST use this schema:

{
  "summary": str,
  "causes": list[str],
  "lessons": list[str],
  "confidence": float,
  "timestamp": str  # ISO8601
}
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


REFLECTION_SCHEMA_KEYS = ("summary", "causes", "lessons", "confidence", "timestamp")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, (list, tuple)):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                t = item.strip()
                if t:
                    out.append(t)
            elif isinstance(item, dict):
                # common nested shapes
                for k in ("text", "cause", "lesson", "summary", "message"):
                    if item.get(k):
                        out.append(str(item[k]).strip())
                        break
                else:
                    out.append(str(item))
            else:
                out.append(str(item))
        return out
    return [str(value)]


def _as_confidence(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v < 0.0:
        return 0.0
    if v > 1.0:
        # allow 0-100 mistaken scale
        if v <= 100.0:
            return round(v / 100.0, 4)
        return 1.0
    return v


def empty_reflection(*, timestamp: Optional[str] = None) -> Dict[str, Any]:
    return {
        "summary": "",
        "causes": [],
        "lessons": [],
        "confidence": 0.0,
        "timestamp": timestamp or _iso_now(),
    }


def normalize_reflection(raw: Any, *, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """
    Normalize any legacy / partial reflection payload into the unified schema.
    Accepts None, str, or dict with alternate field names.
    """
    ts = timestamp or _iso_now()
    if raw is None:
        return empty_reflection(timestamp=ts)

    if isinstance(raw, str):
        text = raw.strip()
        return {
            "summary": text,
            "causes": [],
            "lessons": [],
            "confidence": 0.5 if text else 0.0,
            "timestamp": ts,
        }

    if not isinstance(raw, dict):
        return {
            "summary": str(raw),
            "causes": [],
            "lessons": [],
            "confidence": 0.0,
            "timestamp": ts,
        }

    summary = (
        raw.get("summary")
        or raw.get("reflection_content")
        or raw.get("content")
        or raw.get("text")
        or ""
    )
    if not isinstance(summary, str):
        summary = str(summary)

    causes = _as_str_list(
        raw.get("causes")
        if raw.get("causes") is not None
        else (raw.get("analysis_tags") or {}).get("dominant_causes")
        if isinstance(raw.get("analysis_tags"), dict)
        else raw.get("dominant_causes")
    )
    # reflection_level.causes
    if not causes and isinstance(raw.get("reflection_level"), dict):
        causes = _as_str_list(raw["reflection_level"].get("causes"))

    lessons = _as_str_list(
        raw.get("lessons")
        if raw.get("lessons") is not None
        else raw.get("improvements")
        if raw.get("improvements") is not None
        else (raw.get("analysis_tags") or {}).get("top_improvements")
        if isinstance(raw.get("analysis_tags"), dict)
        else None
    )
    if not lessons and isinstance(raw.get("reflection_level"), dict):
        lessons = _as_str_list(raw["reflection_level"].get("improvements"))

    confidence = _as_confidence(
        raw.get("confidence")
        if raw.get("confidence") is not None
        else raw.get("confidence_score"),
        default=0.0,
    )

    out_ts = raw.get("timestamp") or raw.get("created_at") or ts
    if not isinstance(out_ts, str):
        out_ts = ts

    return {
        "summary": summary.strip(),
        "causes": causes,
        "lessons": lessons,
        "confidence": confidence,
        "timestamp": out_ts,
    }


def validate_reflection(data: Any) -> tuple[bool, str]:
    """Return (ok, error_message)."""
    if not isinstance(data, dict):
        return False, "reflection must be object"
    for key in REFLECTION_SCHEMA_KEYS:
        if key not in data:
            return False, f"missing key: {key}"
    if not isinstance(data["summary"], str):
        return False, "summary must be string"
    if not isinstance(data["causes"], list):
        return False, "causes must be list"
    if not isinstance(data["lessons"], list):
        return False, "lessons must be list"
    try:
        c = float(data["confidence"])
        if c < 0 or c > 1:
            return False, "confidence must be 0..1"
    except (TypeError, ValueError):
        return False, "confidence must be number"
    if not isinstance(data["timestamp"], str) or not data["timestamp"]:
        return False, "timestamp must be non-empty string"
    return True, "ok"


# Hollow / low-insight patterns (quality stage)
_HOLLOW_SUMMARY = re.compile(
    r"^(ok|okay|好的|嗯|無|none|n/a|一般|正常|還可以|沒有特別|無特別)$",
    re.I,
)


def reflection_quality_score(raw: Any) -> Dict[str, Any]:
    """
    Score insight quality of a reflection (0..1).
    Higher when causes + lessons + non-hollow summary present.
    Does not change API schema; for merge/filter/Night Growth.
    """
    r = normalize_reflection(raw)
    summary = (r.get("summary") or "").strip()
    causes = [c for c in (r.get("causes") or []) if str(c).strip()]
    lessons = [x for x in (r.get("lessons") or []) if str(x).strip()]
    conf = float(r.get("confidence") or 0)

    score = 0.0
    flags: List[str] = []
    if summary and len(summary) >= 12 and not _HOLLOW_SUMMARY.match(summary):
        score += 0.28
    else:
        flags.append("weak_summary")
    if causes:
        score += min(0.28, 0.12 * len(causes))
    else:
        flags.append("no_causes")
    if lessons:
        # prefer actionable lessons
        actionable = sum(
            1
            for L in lessons
            if any(k in str(L) for k in ("下次", "應", "可", "避免", "優先", "記住", "should", "next"))
        )
        score += min(0.32, 0.12 * len(lessons) + 0.08 * actionable)
    else:
        flags.append("no_lessons")
    score += 0.12 * conf
    score = max(0.0, min(1.0, score))
    has_insight = score >= 0.45 and "no_lessons" not in flags
    return {
        "score": round(score, 4),
        "has_insight": has_insight,
        "flags": flags,
        "normalized": r,
    }


def merge_reflections(
    *parts: Any,
    prefer_higher_confidence: bool = True,
) -> Dict[str, Any]:
    """
    Merge multiple reflection payloads into one contract object.
    Dedupes causes/lessons; keeps strongest summary; never invents API fields.
    """
    norms = [normalize_reflection(p) for p in parts if p is not None]
    if not norms:
        return empty_reflection()

    # pick best summary by quality then confidence
    best = norms[0]
    best_q = reflection_quality_score(best)["score"]
    for n in norms[1:]:
        q = reflection_quality_score(n)["score"]
        if q > best_q or (
            prefer_higher_confidence
            and abs(q - best_q) < 0.05
            and float(n.get("confidence") or 0) > float(best.get("confidence") or 0)
        ):
            best = n
            best_q = q

    causes: List[str] = []
    lessons: List[str] = []
    seen_c, seen_l = set(), set()
    for n in norms:
        for c in n.get("causes") or []:
            k = str(c).strip()
            if k and k not in seen_c:
                seen_c.add(k)
                causes.append(k)
        for L in n.get("lessons") or []:
            k = str(L).strip()
            if k and k not in seen_l:
                seen_l.add(k)
                lessons.append(k)

    confs = [float(n.get("confidence") or 0) for n in norms]
    conf = max(confs) if confs else 0.0
    # quality-aware confidence floor when insight present
    qmeta = reflection_quality_score(
        {
            "summary": best.get("summary") or "",
            "causes": causes[:8],
            "lessons": lessons[:8],
            "confidence": conf,
            "timestamp": best.get("timestamp") or _iso_now(),
        }
    )
    if qmeta["has_insight"] and conf < 0.55:
        conf = min(0.72, max(conf, 0.55))

    return {
        "summary": (best.get("summary") or "").strip(),
        "causes": causes[:8],
        "lessons": lessons[:8],
        "confidence": conf,
        "timestamp": best.get("timestamp") or _iso_now(),
    }


def is_actionable_reflection(raw: Any, *, min_quality: float = 0.45) -> bool:
    meta = reflection_quality_score(raw)
    return bool(meta["has_insight"] and meta["score"] >= min_quality)


def merge_reflection_into_api_payload(
    payload: Dict[str, Any],
    reflection: Any,
    *,
    include: bool = True,
) -> Dict[str, Any]:
    """Optionally attach normalized reflection to API response dict (non-breaking)."""
    if not include:
        return payload
    norm = normalize_reflection(reflection)
    # only attach if has content
    if norm.get("summary") or norm.get("causes") or norm.get("lessons"):
        payload = dict(payload)
        payload["reflection"] = norm
    return payload
