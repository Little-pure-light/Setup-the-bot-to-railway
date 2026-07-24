"""Memory System V2 — memory type constants and shared models."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# Cognitive memory taxonomy (V2)
MEMORY_TYPES = (
    "episodic",
    "semantic",
    "identity",
    "emotion",
    "reflection",
    "transformation",
    "attention",
    "causal",
)

# V1 conversation rows use this memory_type in Supabase
V1_CONVERSATION_TYPE = "conversation"

# Graph relation vocabulary
GRAPH_RELATIONS = (
    "supports",
    "updates",
    "contradicts",
    "causes",
    "derived_from",
)


@dataclass
class ClassificationResult:
    memory_type: str
    importance: float
    confidence: float
    tags: List[str] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    secondary_types: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryRecord:
    """Normalized V2 memory payload (stored via Supabase document_content / fields)."""

    id: Optional[str] = None
    memory_type: str = "episodic"
    user_id: str = "default_user"
    conversation_id: str = ""
    content: str = ""
    user_message: str = ""
    assistant_message: str = ""
    importance: float = 0.5
    confidence: float = 0.5
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    archived: bool = False
    ai_id: str = "xiaochenguang_v1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clamp01(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def is_v2_type(memory_type: str) -> bool:
    return (memory_type or "") in MEMORY_TYPES
