"""
Decision Engine — rule-based decisions for Night Growth.

Does NOT use LLM as sole judge. Fully unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass
class GrowthDecision:
    save: bool = False
    forget: bool = False
    update_identity: bool = False
    update_attention: bool = False
    form_long_term_knowledge: bool = False
    archive: bool = False
    reasons: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionEngine:
    """
    Answers for Night Growth:
      - worth saving?
      - can forget?
      - update identity?
      - update attention?
      - long-term knowledge?
    """

    def decide(
        self,
        *,
        user_message: str = "",
        assistant_message: str = "",
        classification: Optional[Dict[str, Any]] = None,
        reflection: Optional[Dict[str, Any]] = None,
        semantic_items: Optional[List[Dict[str, Any]]] = None,
        importance: Optional[float] = None,
    ) -> GrowthDecision:
        clf = classification or {}
        mem_type = clf.get("memory_type") or "episodic"
        conf = float(clf.get("confidence") or 0.0)
        imp = float(
            importance
            if importance is not None
            else clf.get("importance")
            if clf.get("importance") is not None
            else 0.5
        )
        tags = list(clf.get("tags") or [])
        secondary = list(clf.get("secondary_types") or [])
        value_tier = (clf.get("value_tier") or "medium").lower()
        should_persist = clf.get("should_persist")
        if should_persist is None:
            should_persist = value_tier != "low"

        d = GrowthDecision(
            scores={
                "importance": imp,
                "confidence": conf,
                "value_tier_high": 1.0 if value_tier == "high" else 0.0,
            }
        )

        um = (user_message or "").strip()
        am = (assistant_message or "").strip()

        # empty / error assistant → forget
        if not am or am.startswith("[ERROR]"):
            d.forget = True
            d.reasons.append("empty_or_error_response")
            return d

        # Quality gate: low-tier chitchat → forget typed permanent path
        if value_tier == "low" or should_persist is False:
            if mem_type == "episodic" and not reflection and not semantic_items:
                d.forget = True
                d.archive = True
                d.save = False
                d.reasons.append("low_value_tier_skip")
                return d

        # identity signals first (even short turns)
        if (
            mem_type == "identity"
            or "identity" in secondary
            or "identity_query" in tags
            or "self_intro" in tags
            or "preference" in tags
        ):
            d.save = True
            d.update_identity = True
            d.reasons.append("identity_signal")

        # high importance or attention tags
        if imp >= 0.7 or "attention" in tags or mem_type == "attention":
            d.save = True
            d.update_attention = True
            d.reasons.append("high_importance_or_attention")

        # trivial chit-chat → forget (only if no stronger signals)
        if (
            not d.save
            and len(um) < 4
            and len(am) < 8
            and not reflection
            and not semantic_items
        ):
            d.forget = True
            d.reasons.append("trivial_chitchat")
            return d

        # reflection present with actionable insight (not hollow summary)
        refl = reflection or {}
        if refl.get("summary") or refl.get("causes") or refl.get("lessons"):
            try:
                from backend.modules.reflection_contract import (
                    is_actionable_reflection,
                    reflection_quality_score,
                )

                q = reflection_quality_score(refl)
                actionable = is_actionable_reflection(refl)
            except Exception:
                q = {"score": 0.4, "has_insight": bool(refl.get("lessons"))}
                actionable = bool(refl.get("lessons"))

            if actionable or float(q.get("score") or 0) >= 0.45:
                d.save = True
                d.form_long_term_knowledge = True
                d.reasons.append("has_actionable_reflection")
            else:
                d.reasons.append("hollow_reflection_skipped_for_identity")

            conf_r = float(refl.get("confidence") or 0)
            # Do NOT lower threshold: still require lessons + confidence for identity
            if conf_r >= 0.55 and refl.get("lessons") and actionable:
                d.update_identity = True
                d.reasons.append("reflection_lessons")
            elif conf_r >= 0.55 and refl.get("lessons") and not actionable:
                d.reasons.append("lessons_present_but_low_insight")

        # semantic knowledge items
        if semantic_items:
            d.save = True
            d.form_long_term_knowledge = True
            d.reasons.append("semantic_items")

        # transformation / causal always worth a save as typed memory
        if mem_type in ("transformation", "causal", "semantic", "emotion"):
            d.save = True
            d.reasons.append(f"type_{mem_type}")

        # episodic medium — save if not already forget
        if mem_type == "episodic" and imp >= 0.45:
            d.save = True
            d.reasons.append("episodic_worth_keeping")

        # low value archive path
        if imp < 0.35 and conf < 0.4 and not reflection and not semantic_items:
            d.forget = True
            d.archive = True
            d.save = False
            d.reasons.append("low_value_archive")

        # if both save and forget flags, prefer save
        if d.save and d.forget:
            d.forget = False
            d.reasons.append("prefer_save_over_forget")

        if not d.reasons:
            d.reasons.append("default_no_action")

        return d
