"""
MemoryClassifier — classify interaction into cognitive memory types.

Quality Improvement stage:
  High / Medium / Low value tiers → write less, remember better.
  No new memory types. No new APIs.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.modules.memory_types import (
    ClassificationResult,
    MEMORY_TYPES,
    clamp01,
)

# Query / content heuristics (zh + en)
_IDENTITY_PAT = re.compile(
    r"(你是誰|你叫什麼|你的名字|身份|persona|who are you|your name|小宸光)",
    re.I,
)
_SELF_INTRO_PAT = re.compile(
    r"(我叫|我的名字|我是|請叫我|稱呼我|my name is|i am |i'm )",
    re.I,
)
_PREF_PAT = re.compile(
    r"(我喜歡|我不喜歡|我偏好|我討厭|請記住我|以後都|prefer|i like|i love|i hate)",
    re.I,
)
_SEMANTIC_PAT = re.compile(
    r"(什麼是|如何|怎麼|知識|定義|原理|為什麼|what is|how to|explain|定義|專案代號|請記住[：:])",
    re.I,
)
_EPISODIC_PAT = re.compile(
    r"(記得|上次|之前|那天|我們說過|還記得|yesterday|last time|remember when)",
    re.I,
)
_EMOTION_PAT = re.compile(
    r"(心情|難過|開心|生氣|害怕|累|焦慮|emotion|feel|sad|happy|angry)",
    re.I,
)
_REFLECT_PAT = re.compile(
    r"(反思|反省|改進|學到|reflect|lesson|improve)",
    re.I,
)
_TRANSFORM_PAT = re.compile(
    r"(人格|性格|變得|成長|轉變|personality|become|growth)",
    re.I,
)
_ATTENTION_PAT = re.compile(
    r"(重點|注意|別忘|重要|focus|priority|important|記住這個|務必)",
    re.I,
)
_CAUSAL_PAT = re.compile(
    r"(因為|所以|導致|造成|原因|結果|because|therefore|cause|due to)",
    re.I,
)
# Low-value / chitchat
_CHITCHAT_PAT = re.compile(
    r"^(你好|您好|嗨|哈囉|哈喽|hi|hello|hey|早安|午安|晚安|在嗎|在不在|"
    r"哈哈+|呵呵+|嗯+|喔+|哦+|好的?|ok|okay|thanks|thank you|謝謝|感謝|"
    r"再見|拜拜|bye|lol|www+|～+|~+)$",
    re.I,
)
_COURTESY_PAT = re.compile(
    r"^(謝謝你?|感謝|麻煩了|辛苦了|不好意思|抱歉|對不起)[！!。.~～]*$",
    re.I,
)


class MemoryClassifier:
    """Rule-based classifier (no extra LLM call — safe for production path)."""

    # Tier thresholds (importance after scoring)
    HIGH_MIN = 0.72
    MEDIUM_MIN = 0.48

    def classify(
        self,
        *,
        conversation: Optional[Dict[str, Any]] = None,
        emotion: Optional[Dict[str, Any]] = None,
        reflection: Optional[Dict[str, Any]] = None,
        tool_result: Optional[Any] = None,
        document: Optional[str] = None,
    ) -> ClassificationResult:
        conversation = conversation or {}
        user_text = str(
            conversation.get("user_message")
            or conversation.get("user_input")
            or conversation.get("text")
            or ""
        ).strip()
        bot_text = str(
            conversation.get("assistant_message")
            or conversation.get("bot_response")
            or ""
        ).strip()
        blob = f"{user_text}\n{bot_text}\n{document or ''}"

        tags: List[str] = []
        secondary: List[str] = []
        relations: List[Dict[str, Any]] = []
        scores: Dict[str, float] = {t: 0.0 for t in MEMORY_TYPES}

        low_value_reason: Optional[str] = None
        if self._is_low_value_turn(user_text, bot_text, reflection, emotion, document, tool_result):
            low_value_reason = "chitchat_or_courtesy_or_trivial"
            tags.append("low_value")

        # --- reflection payload ---
        has_refl_body = bool(
            reflection
            and (
                reflection.get("summary")
                or reflection.get("lessons")
                or reflection.get("causes")
                or reflection.get("improvements")
            )
        )
        if has_refl_body:
            scores["reflection"] += 1.05  # beat generic semantic keyword hits
            tags.append("has_reflection")
            conf_r = clamp01(reflection.get("confidence", 0.6))
            lessons = reflection.get("lessons") or reflection.get("improvements")
            if conf_r >= 0.55 and (lessons or reflection.get("causes")):
                scores["transformation"] += 0.4
                secondary.append("transformation")
                relations.append(
                    {
                        "relation": "derived_from",
                        "from": "reflection",
                        "to": "transformation",
                    }
                )

        # --- emotion ---
        if emotion and emotion.get("dominant_emotion"):
            emo_name = str(emotion.get("dominant_emotion") or "neutral")
            intensity = clamp01(emotion.get("intensity", 0.5))
            if emo_name not in ("neutral", "", "None") and intensity >= 0.45:
                scores["emotion"] += 0.55 + 0.25 * intensity
                tags.append(f"emotion:{emo_name}")
            if _EMOTION_PAT.search(blob):
                scores["emotion"] += 0.25

        # --- document / tool ---
        if document and str(document).strip():
            scores["semantic"] += 0.75
            tags.append("document")
            relations.append(
                {"relation": "supports", "from": "document", "to": "semantic"}
            )
        if tool_result is not None:
            scores["semantic"] += 0.4
            tags.append("tool")
            secondary.append("episodic")

        # --- text heuristics ---
        if _IDENTITY_PAT.search(blob):
            scores["identity"] += 0.95
            tags.append("identity_query")
        if _SELF_INTRO_PAT.search(user_text):
            scores["identity"] += 0.85
            tags.append("self_intro")
        if _PREF_PAT.search(user_text):
            scores["semantic"] += 0.65
            scores["attention"] += 0.35
            tags.append("preference")
        if _SEMANTIC_PAT.search(blob):
            scores["semantic"] += 0.7
        if _EPISODIC_PAT.search(blob):
            scores["episodic"] += 0.75
        if _EMOTION_PAT.search(blob):
            scores["emotion"] += 0.5
        if _REFLECT_PAT.search(blob):
            scores["reflection"] += 0.6
        if _TRANSFORM_PAT.search(blob):
            scores["transformation"] += 0.65
        if _ATTENTION_PAT.search(blob):
            scores["attention"] += 0.85
            tags.append("attention")
        if _CAUSAL_PAT.search(blob):
            scores["causal"] += 0.7
            relations.append({"relation": "causes", "hint": "causal_language"})

        # Default episodic only for substantive dialogue (not pure chitchat)
        if (user_text or bot_text) and not low_value_reason:
            scores["episodic"] = max(scores["episodic"], 0.45)

        # Pick primary type
        primary = max(scores.items(), key=lambda x: x[1])
        memory_type = primary[0] if primary[1] > 0 else "episodic"
        if low_value_reason and primary[1] < 0.55:
            memory_type = "episodic"
        raw_conf = primary[1]
        confidence = clamp01(0.35 + min(raw_conf, 1.5) / 2.0)

        importance = self._importance(
            user_text=user_text,
            bot_text=bot_text,
            emotion=emotion,
            reflection=reflection,
            memory_type=memory_type,
            tags=tags,
            low_value=bool(low_value_reason),
        )

        value_tier, should_persist = self._value_policy(
            importance=importance,
            memory_type=memory_type,
            tags=tags,
            low_value=bool(low_value_reason),
            reflection=reflection,
            user_text=user_text,
        )
        if value_tier == "low":
            tags.append("tier:low")
        elif value_tier == "high":
            tags.append("tier:high")
        else:
            tags.append("tier:medium")

        for t, s in scores.items():
            if t != memory_type and s >= 0.55 and t not in secondary:
                secondary.append(t)

        return ClassificationResult(
            memory_type=memory_type,
            importance=importance,
            confidence=confidence,
            tags=sorted(set(tags)),
            relations=relations,
            secondary_types=secondary[:4],
            value_tier=value_tier,
            should_persist=should_persist,
        )

    def _is_low_value_turn(
        self,
        user_text: str,
        bot_text: str,
        reflection: Optional[Dict[str, Any]],
        emotion: Optional[Dict[str, Any]],
        document: Optional[str],
        tool_result: Optional[Any],
    ) -> bool:
        if document and str(document).strip():
            return False
        if tool_result is not None:
            return False
        if reflection and (
            reflection.get("lessons")
            or (reflection.get("summary") and len(str(reflection.get("summary"))) > 20)
        ):
            return False
        if emotion and emotion.get("dominant_emotion") not in (
            None,
            "neutral",
            "",
        ):
            if clamp01(emotion.get("intensity", 0)) >= 0.55:
                return False

        u = (user_text or "").strip()
        if not u:
            return True
        if _CHITCHAT_PAT.match(u) or _COURTESY_PAT.match(u):
            return True
        # very short non-substantive
        if len(u) <= 3 and not _ATTENTION_PAT.search(u) and not _PREF_PAT.search(u):
            return True
        if len(u) <= 8 and not any(
            p.search(u)
            for p in (
                _PREF_PAT,
                _SELF_INTRO_PAT,
                _SEMANTIC_PAT,
                _ATTENTION_PAT,
                _EPISODIC_PAT,
                _EMOTION_PAT,
                _IDENTITY_PAT,
            )
        ):
            # short small talk
            if re.match(r"^[\W\d\s]+$", u):
                return True
        return False

    def _value_policy(
        self,
        *,
        importance: float,
        memory_type: str,
        tags: List[str],
        low_value: bool,
        reflection: Optional[Dict[str, Any]],
        user_text: str,
    ) -> Tuple[str, bool]:
        """
        High / Medium / Low write strategy.
        should_persist → whether to write typed V2 permanent memory.
        V1 conversation continuity is independent (handled by MemoryManager).
        """
        if low_value and memory_type == "episodic" and not reflection:
            return "low", False

        # Durable user facts always worth a typed row (quality > volume)
        if "self_intro" in tags or "preference" in tags or "attention" in tags:
            if importance >= 0.62 or "attention" in tags:
                return "high", True
            return "medium", True
        if "has_reflection" in tags and importance >= self.MEDIUM_MIN:
            return "high" if importance >= self.HIGH_MIN else "medium", True

        high_type = memory_type in (
            "identity",
            "attention",
            "transformation",
            "reflection",
            "semantic",
        )
        if importance >= self.HIGH_MIN or (high_type and importance >= 0.62):
            return "high", True
        if memory_type in ("identity", "attention") and importance >= 0.55:
            return "high", True

        if importance >= self.MEDIUM_MIN:
            if memory_type == "episodic" and importance < 0.55:
                return "low", False
            return "medium", True

        if high_type and importance >= 0.42:
            return "medium", True
        return "low", False

    def _importance(
        self,
        *,
        user_text: str,
        bot_text: str,
        emotion: Optional[Dict[str, Any]],
        reflection: Optional[Dict[str, Any]],
        memory_type: str,
        tags: List[str],
        low_value: bool,
    ) -> float:
        if low_value:
            return clamp01(0.12 + min(len(user_text), 20) / 200.0)

        # Length helps only up to a point; long chitchat shouldn't win
        length_score = min(0.28, (len(user_text) + min(len(bot_text), 400)) / 1000.0)
        emo = 0.0
        if emotion:
            emo = 0.22 * clamp01(emotion.get("intensity", 0.5))
            if emotion.get("dominant_emotion") not in (None, "neutral"):
                emo += 0.12
        ref = 0.0
        if reflection:
            ref = 0.12
            if reflection.get("lessons"):
                ref += 0.12
            conf = clamp01(reflection.get("confidence", 0))
            ref += 0.1 * conf
        type_boost = {
            "identity": 0.22,
            "attention": 0.2,
            "transformation": 0.16,
            "causal": 0.12,
            "reflection": 0.14,
            "semantic": 0.12,
            "emotion": 0.12,
            "episodic": 0.04,
        }.get(memory_type, 0.05)
        tag_boost = 0.0
        if "self_intro" in tags:
            tag_boost += 0.22
        if "preference" in tags:
            tag_boost += 0.22
        if "attention" in tags:
            tag_boost += 0.14
        if "document" in tags:
            tag_boost += 0.1
        return clamp01(0.22 + length_score + emo + ref + type_boost + tag_boost)
