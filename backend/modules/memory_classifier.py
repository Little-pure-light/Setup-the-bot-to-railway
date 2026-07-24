"""
MemoryClassifier — classify interaction into cognitive memory types.

Input: conversation / emotion / reflection / tool_result / document
Output: memory_type, importance, confidence, tags, relations
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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
_SEMANTIC_PAT = re.compile(
    r"(什麼是|如何|怎麼|知識|定義|原理|為什麼|what is|how to|explain|定義)",
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
    r"(反思|反省|改進|學到|反思|reflect|lesson|improve)",
    re.I,
)
_TRANSFORM_PAT = re.compile(
    r"(人格|性格|變得|成長|轉變|personality|become|growth)",
    re.I,
)
_ATTENTION_PAT = re.compile(
    r"(重點|注意|別忘|重要|focus|priority|important|記住這個)",
    re.I,
)
_CAUSAL_PAT = re.compile(
    r"(因為|所以|導致|造成|原因|結果|because|therefore|cause|due to)",
    re.I,
)


class MemoryClassifier:
    """Rule-based classifier (no extra LLM call — safe for production path)."""

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
        )
        bot_text = str(
            conversation.get("assistant_message")
            or conversation.get("bot_response")
            or ""
        )
        blob = f"{user_text}\n{bot_text}\n{document or ''}"

        tags: List[str] = []
        secondary: List[str] = []
        relations: List[Dict[str, Any]] = []
        scores: Dict[str, float] = {t: 0.0 for t in MEMORY_TYPES}

        # --- reflection payload wins for type ---
        if reflection:
            scores["reflection"] += 0.9
            tags.append("has_reflection")
            conf_r = clamp01(reflection.get("confidence", 0.6))
            if conf_r >= 0.5:
                scores["transformation"] += 0.35
                secondary.append("transformation")
                relations.append(
                    {"relation": "derived_from", "from": "reflection", "to": "transformation"}
                )

        # --- emotion ---
        if emotion and emotion.get("dominant_emotion"):
            scores["emotion"] += 0.55 + 0.2 * clamp01(emotion.get("intensity", 0.5))
            tags.append(f"emotion:{emotion.get('dominant_emotion')}")
            if _EMOTION_PAT.search(blob):
                scores["emotion"] += 0.25

        # --- document / tool ---
        if document and str(document).strip():
            scores["semantic"] += 0.7
            tags.append("document")
            relations.append({"relation": "supports", "from": "document", "to": "semantic"})
        if tool_result is not None:
            scores["semantic"] += 0.45
            tags.append("tool")
            secondary.append("episodic")

        # --- text heuristics ---
        if _IDENTITY_PAT.search(blob):
            scores["identity"] += 0.95
            tags.append("identity_query")
        if _SEMANTIC_PAT.search(blob):
            scores["semantic"] += 0.7
        if _EPISODIC_PAT.search(blob):
            scores["episodic"] += 0.75
        if _EMOTION_PAT.search(blob):
            scores["emotion"] += 0.55
        if _REFLECT_PAT.search(blob):
            scores["reflection"] += 0.6
        if _TRANSFORM_PAT.search(blob):
            scores["transformation"] += 0.65
        if _ATTENTION_PAT.search(blob):
            scores["attention"] += 0.8
            tags.append("attention")
        if _CAUSAL_PAT.search(blob):
            scores["causal"] += 0.7
            relations.append({"relation": "causes", "hint": "causal_language"})

        # Default: every dialogue turn is at least episodic
        if user_text or bot_text:
            scores["episodic"] = max(scores["episodic"], 0.5)

        # Pick primary type
        primary = max(scores.items(), key=lambda x: x[1])
        memory_type = primary[0] if primary[1] > 0 else "episodic"
        raw_conf = primary[1]
        # normalize confidence into 0.35–0.98
        confidence = clamp01(0.35 + min(raw_conf, 1.5) / 2.0)

        importance = self._importance(
            user_text=user_text,
            bot_text=bot_text,
            emotion=emotion,
            reflection=reflection,
            memory_type=memory_type,
        )

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
        )

    def _importance(
        self,
        *,
        user_text: str,
        bot_text: str,
        emotion: Optional[Dict[str, Any]],
        reflection: Optional[Dict[str, Any]],
        memory_type: str,
    ) -> float:
        length_score = min(0.4, (len(user_text) + len(bot_text)) / 800.0)
        emo = 0.0
        if emotion:
            emo = 0.25 * clamp01(emotion.get("intensity", 0.5))
            if emotion.get("dominant_emotion") not in (None, "neutral"):
                emo += 0.1
        ref = 0.15 if reflection else 0.0
        type_boost = {
            "identity": 0.2,
            "attention": 0.18,
            "transformation": 0.15,
            "causal": 0.12,
            "reflection": 0.12,
            "semantic": 0.08,
            "emotion": 0.1,
            "episodic": 0.05,
        }.get(memory_type, 0.05)
        return clamp01(0.25 + length_score + emo + ref + type_boost)
