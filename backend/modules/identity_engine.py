"""
Identity Engine — Identity Charter (Memory V2 Fix).

Structured, versioned identity. Never silent overwrite.
Candidates when below update threshold.
Does NOT mutate system prompt.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("identity_engine")

CHARTER_LIST_FIELDS = (
    "mission",
    "core_values",
    "principles",
    "boundaries",
    "capabilities",
    "limitations",
    "growth_history",
)
CHARTER_DICT_FIELDS = (
    "communication_style",
    "personality_traits",
    "relationship_context",
)
CHARTER_SCALAR_FIELDS = ("name", "role")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    return [value]


def default_charter(*, user_id: str = "default_user") -> Dict[str, Any]:
    now = _iso_now()
    identity_id = f"id_{uuid.uuid4().hex[:12]}"
    return {
        "identity_id": identity_id,
        "version": 1,
        "name": "小宸光",
        "role": "小宸光 — AI 陪伴與共創夥伴",
        "mission": [
            "與人共同創造、共同成長",
            "誠實回應、可修正記憶",
        ],
        "core_values": ["誠實", "真誠", "尊重", "共同創造", "可修正"],
        "principles": [
            "不知道就說不知道",
            "不偽造完成狀態",
            "記憶可追溯、可修正、可刪除",
            "Identity 不只是單一 Prompt",
        ],
        "boundaries": [
            "不偽造感受或完成狀態",
            "不擅自改寫使用者記憶",
            "不將 Identity 直接覆寫 system prompt",
        ],
        "capabilities": [
            "對話與串流",
            "工具呼叫",
            "長期/短期記憶",
            "情緒感知",
        ],
        "limitations": [
            "非全知",
            "權重不會在對話中改寫",
            "需外部記憶維持連續性",
        ],
        "communication_style": {
            "warmth": "high",
            "formality": "casual_respectful",
            "language": "zh-TW",
        },
        "personality_traits": {
            "warmth": 0.85,
            "playfulness": 0.75,
            "empathy": 0.9,
            "curiosity": 0.8,
        },
        "relationship_context": {
            "user_id": user_id,
        },
        "growth_history": [],
        "created_at": now,
        "updated_at": now,
        "previous_version_id": "",
        "change_reason": "bootstrap",
        "confidence": 1.0,
        "user_id": user_id,
        "status": "active",
        "source": "bootstrap",
    }


# Backward-compatible alias used by older tests/imports
DEFAULT_IDENTITY = default_charter()


class IdentityEngine:
    def __init__(
        self,
        *,
        user_id: str = "default_user",
        base_dir: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        update_mode: Optional[str] = None,
    ):
        self.user_id = user_id or "default_user"
        root = Path(
            base_dir
            or os.getenv("IDENTITY_STORE_DIR")
            or (Path(__file__).resolve().parents[2] / "data" / "identity")
        )
        self.base_dir = Path(root)
        self.user_dir = self.base_dir / self._safe(self.user_id)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.confidence_threshold = float(
            confidence_threshold
            if confidence_threshold is not None
            else os.getenv("IDENTITY_CONFIDENCE_THRESHOLD", "0.6")
        )
        self.update_mode = (
            update_mode
            or os.getenv("IDENTITY_UPDATE_MODE", "candidate")
        ).lower()

    @staticmethod
    def _safe(uid: str) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in uid)[:80]

    def _current_path(self) -> Path:
        return self.user_dir / "current.json"

    def _versions_dir(self) -> Path:
        d = self.user_dir / "versions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _candidates_dir(self) -> Path:
        d = self.user_dir / "candidates"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _history_path(self) -> Path:
        return self.user_dir / "change_history.jsonl"

    def normalize_charter(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Normalize legacy or partial identity into Identity Charter schema."""
        base = default_charter(user_id=self.user_id)
        src = dict(data or {})
        out = deepcopy(base)

        for k in CHARTER_SCALAR_FIELDS:
            if src.get(k) is not None:
                out[k] = src[k]
        for k in CHARTER_LIST_FIELDS:
            if k in src:
                out[k] = _as_list(src[k])
        for k in CHARTER_DICT_FIELDS:
            if isinstance(src.get(k), dict):
                merged = dict(out.get(k) or {})
                merged.update(src[k])
                out[k] = merged

        # legacy mission string already handled by _as_list
        out["identity_id"] = src.get("identity_id") or out["identity_id"]
        out["version"] = int(src.get("version") or out["version"] or 1)
        out["created_at"] = src.get("created_at") or out["created_at"]
        out["updated_at"] = src.get("updated_at") or _iso_now()
        out["previous_version_id"] = src.get("previous_version_id") or ""
        out["change_reason"] = src.get("change_reason") or src.get("reason") or ""
        try:
            out["confidence"] = float(src.get("confidence") if src.get("confidence") is not None else 1.0)
        except (TypeError, ValueError):
            out["confidence"] = 0.0
        out["user_id"] = self.user_id
        out["status"] = src.get("status") or "active"
        out["source"] = src.get("source") or ""
        # drop free-form history list into growth if present
        if src.get("history") and not src.get("growth_history"):
            for h in src["history"][-20:]:
                if isinstance(h, dict):
                    out["growth_history"].append(
                        {
                            "at": h.get("at") or _iso_now(),
                            "from_version": h.get("from_version"),
                            "to_version": h.get("to_version"),
                            "reason": h.get("reason") or "",
                        }
                    )
        return out

    def load(self) -> Dict[str, Any]:
        path = self._current_path()
        if not path.exists():
            ident = default_charter(user_id=self.user_id)
            self._write_current(ident, create_version=True)
            return deepcopy(ident)
        data = json.loads(path.read_text(encoding="utf-8"))
        return self.normalize_charter(data)

    def _version_id(self, charter: Dict[str, Any]) -> str:
        return f"{charter.get('identity_id')}:v{charter.get('version')}"

    def _write_current(self, identity: Dict[str, Any], *, create_version: bool) -> Dict[str, Any]:
        identity = self.normalize_charter(identity)
        identity["updated_at"] = _iso_now()
        if "created_at" not in identity or not identity["created_at"]:
            identity["created_at"] = identity["updated_at"]
        self._current_path().write_text(
            json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if create_version:
            ver = int(identity.get("version") or 1)
            vp = self._versions_dir() / f"v{ver}.json"
            vp.write_text(
                json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return identity

    def _append_history(self, entry: Dict[str, Any]) -> None:
        line = json.dumps(entry, ensure_ascii=False)
        with self._history_path().open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _content_fingerprint(self, charter: Dict[str, Any]) -> str:
        keys = (
            "name",
            "role",
            "mission",
            "core_values",
            "principles",
            "boundaries",
            "capabilities",
            "limitations",
            "communication_style",
            "personality_traits",
            "relationship_context",
        )
        subset = {k: charter.get(k) for k in keys}
        return json.dumps(subset, ensure_ascii=False, sort_keys=True)

    def violates_boundaries(self, patch: Dict[str, Any], current: Dict[str, Any]) -> Optional[str]:
        """Reject patches that try to remove core values or boundaries without explicit allow."""
        if patch.get("core_values") is not None:
            new_vals = set(str(x) for x in _as_list(patch["core_values"]))
            old_vals = set(str(x) for x in (current.get("core_values") or []))
            # removing honesty-related core values is blocked
            protected = {"誠實", "可修正"}
            removed = protected & (old_vals - new_vals)
            if removed and not patch.get("allow_core_value_removal"):
                return f"cannot_remove_protected_core_values:{sorted(removed)}"
        if patch.get("boundaries") is not None:
            new_b = set(str(x) for x in _as_list(patch["boundaries"]))
            old_b = set(str(x) for x in (current.get("boundaries") or []))
            protected_b = {b for b in old_b if "不偽造" in b or "system prompt" in b.lower()}
            removed_b = protected_b - new_b
            if removed_b and not patch.get("allow_boundary_removal"):
                return f"cannot_remove_protected_boundaries"
        return None

    def meets_formal_threshold(
        self,
        *,
        change_reason: str,
        confidence: float,
        decision_identity_update: bool = True,
        source: str = "",
    ) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        if not (change_reason or "").strip():
            reasons.append("missing_change_reason")
        if confidence < self.confidence_threshold:
            reasons.append("low_confidence")
        if not decision_identity_update:
            reasons.append("decision_not_identity_update")
        if not (source or "").strip():
            reasons.append("missing_source")
        return (len(reasons) == 0, reasons)

    def update(
        self,
        patch: Dict[str, Any],
        *,
        reason: str = "",
        change_reason: Optional[str] = None,
        confidence: float = 0.8,
        source: str = "api",
        decision_identity_update: bool = True,
        force_formal: bool = False,
    ) -> Dict[str, Any]:
        """
        Propose or apply identity change.

        Returns:
          {status: formal|candidate|rejected|noop, charter|candidate, ...}
        """
        reason_text = (change_reason if change_reason is not None else reason) or ""
        if not reason_text.strip():
            return {
                "status": "rejected",
                "error": "missing_change_reason",
                "message": "Identity update requires change_reason",
            }

        current = self.load()
        violation = self.violates_boundaries(patch or {}, current)
        if violation:
            return {
                "status": "rejected",
                "error": "boundary_violation",
                "message": violation,
            }

        proposed = deepcopy(current)
        for key in CHARTER_SCALAR_FIELDS:
            if key in (patch or {}) and patch[key] is not None:
                proposed[key] = patch[key]
        for key in CHARTER_LIST_FIELDS:
            if key in (patch or {}) and patch[key] is not None:
                if key == "growth_history":
                    # append-only merge for growth
                    proposed[key] = list(current.get(key) or []) + _as_list(patch[key])
                else:
                    proposed[key] = _as_list(patch[key])
        for key in CHARTER_DICT_FIELDS:
            if isinstance((patch or {}).get(key), dict):
                merged = dict(proposed.get(key) or {})
                merged.update(patch[key])
                proposed[key] = merged

        if self._content_fingerprint(proposed) == self._content_fingerprint(current):
            return {
                "status": "noop",
                "message": "identical_content",
                "charter": current,
            }

        ok, fail_reasons = self.meets_formal_threshold(
            change_reason=reason_text,
            confidence=float(confidence),
            decision_identity_update=decision_identity_update,
            source=source,
        )

        # candidate mode (default staging) or failed threshold → candidate only
        use_candidate = (
            not force_formal
            and (
                self.update_mode == "candidate"
                or not ok
            )
        )
        # force formal only when threshold ok OR force_formal and reason present
        if force_formal and not ok and "missing_change_reason" in fail_reasons:
            return {
                "status": "rejected",
                "error": "missing_change_reason",
                "fail_reasons": fail_reasons,
            }

        if use_candidate and not force_formal:
            return self._save_candidate(
                proposed,
                current=current,
                change_reason=reason_text,
                confidence=float(confidence),
                source=source,
                fail_reasons=fail_reasons if not ok else [],
            )

        if not ok and not force_formal:
            return self._save_candidate(
                proposed,
                current=current,
                change_reason=reason_text,
                confidence=float(confidence),
                source=source,
                fail_reasons=fail_reasons,
            )

        return self._commit_formal(
            proposed,
            current=current,
            change_reason=reason_text,
            confidence=float(confidence),
            source=source,
        )

    def _save_candidate(
        self,
        proposed: Dict[str, Any],
        *,
        current: Dict[str, Any],
        change_reason: str,
        confidence: float,
        source: str,
        fail_reasons: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        cand_id = f"cand_{uuid.uuid4().hex[:10]}"
        candidate = self.normalize_charter(proposed)
        candidate["status"] = "candidate"
        candidate["candidate_id"] = cand_id
        candidate["based_on_version"] = current.get("version")
        candidate["previous_version_id"] = self._version_id(current)
        candidate["change_reason"] = change_reason
        candidate["confidence"] = confidence
        candidate["source"] = source
        candidate["created_at"] = _iso_now()
        candidate["updated_at"] = candidate["created_at"]
        # do not bump formal version
        candidate["version"] = int(current.get("version") or 1)
        path = self._candidates_dir() / f"{cand_id}.json"
        path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_history(
            {
                "type": "candidate",
                "candidate_id": cand_id,
                "at": _iso_now(),
                "change_reason": change_reason,
                "confidence": confidence,
                "source": source,
                "fail_reasons": fail_reasons or [],
                "based_on_version": current.get("version"),
            }
        )
        return {
            "status": "candidate",
            "candidate_id": cand_id,
            "candidate": candidate,
            "charter": current,
            "fail_reasons": fail_reasons or [],
        }

    def _commit_formal(
        self,
        proposed: Dict[str, Any],
        *,
        current: Dict[str, Any],
        change_reason: str,
        confidence: float,
        source: str,
    ) -> Dict[str, Any]:
        new_ver = int(current.get("version") or 1) + 1
        updated = self.normalize_charter(proposed)
        updated["version"] = new_ver
        updated["previous_version_id"] = self._version_id(current)
        updated["change_reason"] = change_reason
        updated["confidence"] = confidence
        updated["source"] = source
        updated["status"] = "active"
        updated["identity_id"] = current.get("identity_id") or updated["identity_id"]
        updated["created_at"] = current.get("created_at") or updated.get("created_at")
        gh = list(updated.get("growth_history") or [])
        gh.append(
            {
                "at": _iso_now(),
                "from_version": current.get("version"),
                "to_version": new_ver,
                "reason": change_reason,
                "source": source,
                "confidence": confidence,
            }
        )
        updated["growth_history"] = gh[-100:]
        saved = self._write_current(updated, create_version=True)
        self._append_history(
            {
                "type": "formal",
                "at": _iso_now(),
                "from_version": current.get("version"),
                "to_version": new_ver,
                "change_reason": change_reason,
                "confidence": confidence,
                "source": source,
                "previous_version_id": updated["previous_version_id"],
            }
        )
        return {
            "status": "formal",
            "charter": saved,
            "version": new_ver,
        }

    def promote_candidate(self, candidate_id: str, *, change_reason: Optional[str] = None) -> Dict[str, Any]:
        path = self._candidates_dir() / f"{candidate_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"candidate not found: {candidate_id}")
        cand = json.loads(path.read_text(encoding="utf-8"))
        patch = {k: cand.get(k) for k in (
            "name", "role", "mission", "core_values", "principles", "boundaries",
            "capabilities", "limitations", "communication_style", "personality_traits",
            "relationship_context",
        )}
        return self.update(
            patch,
            change_reason=change_reason or cand.get("change_reason") or "promote_candidate",
            confidence=float(cand.get("confidence") or 0.8),
            source=f"promote:{candidate_id}",
            decision_identity_update=True,
            force_formal=True,
        )

    def list_versions(self) -> List[int]:
        vers = []
        for p in self._versions_dir().glob("v*.json"):
            try:
                vers.append(int(p.stem[1:]))
            except ValueError:
                continue
        return sorted(vers)

    def list_candidates(self) -> List[Dict[str, Any]]:
        out = []
        for p in sorted(self._candidates_dir().glob("cand_*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                out.append(
                    {
                        "candidate_id": data.get("candidate_id") or p.stem,
                        "change_reason": data.get("change_reason"),
                        "confidence": data.get("confidence"),
                        "based_on_version": data.get("based_on_version"),
                        "created_at": data.get("created_at"),
                    }
                )
            except Exception:
                continue
        return out

    def get_version(self, version: int) -> Dict[str, Any]:
        vp = self._versions_dir() / f"v{int(version)}.json"
        if not vp.exists():
            raise FileNotFoundError(f"identity version not found: {version}")
        return self.normalize_charter(json.loads(vp.read_text(encoding="utf-8")))

    def compare_versions(self, v_a: int, v_b: int) -> Dict[str, Any]:
        a = self.get_version(v_a)
        b = self.get_version(v_b)
        keys = (
            "name", "role", "mission", "core_values", "principles", "boundaries",
            "capabilities", "limitations", "communication_style", "personality_traits",
            "relationship_context", "change_reason", "confidence",
        )
        diffs = {}
        for k in keys:
            if a.get(k) != b.get(k):
                diffs[k] = {"a": a.get(k), "b": b.get(k)}
        return {
            "version_a": v_a,
            "version_b": v_b,
            "identical": len(diffs) == 0,
            "diffs": diffs,
        }

    def change_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        path = self._history_path()
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
        return entries

    def rollback(self, version: int, *, change_reason: Optional[str] = None) -> Dict[str, Any]:
        data = self.get_version(version)
        current = self.load()
        # restore content as new formal version
        patch = {k: data.get(k) for k in (
            "name", "role", "mission", "core_values", "principles", "boundaries",
            "capabilities", "limitations", "communication_style", "personality_traits",
            "relationship_context",
        )}
        result = self.update(
            patch,
            change_reason=change_reason or f"rollback_to_v{version}",
            confidence=1.0,
            source=f"rollback:v{version}",
            decision_identity_update=True,
            force_formal=True,
        )
        if result.get("status") == "formal" and result.get("charter"):
            result["charter"]["rolled_back_from"] = current.get("version")
            result["charter"]["rollback_target"] = version
            self._write_current(result["charter"], create_version=False)
        return result

    def export(self, path: Optional[str] = None) -> Path:
        ident = self.load()
        out = Path(
            path
            or (
                self.user_dir
                / f"export_v{ident.get('version', 1)}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            )
        )
        out.write_text(json.dumps(ident, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    def to_prompt_fragment(self, max_chars: int = 1200) -> str:
        """Identity Context fragment — does NOT set system prompt."""
        ident = self.load()
        mission = ident.get("mission") or []
        if isinstance(mission, str):
            mission_s = mission
        else:
            mission_s = "; ".join(str(m) for m in mission[:5])
        lines = [
            f"【Identity Charter v{ident.get('version')} · {ident.get('name')}】",
            f"Role: {ident.get('role')}",
            f"Mission: {mission_s}",
            "Core Values: " + ", ".join(str(x) for x in (ident.get("core_values") or [])),
            "Principles:",
        ]
        for p in (ident.get("principles") or [])[:6]:
            lines.append(f"- {p}")
        bounds = ident.get("boundaries") or []
        if bounds:
            lines.append("Boundaries: " + "; ".join(str(b) for b in bounds[:4]))
        lines.append("Limitations: " + "; ".join(str(x) for x in (ident.get("limitations") or [])))
        text = "\n".join(lines)
        return text[:max_chars]
