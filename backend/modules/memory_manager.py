"""
MemoryManager — V2 public API (Strangler over V1 MemorySystem).

Responsibilities: save / retrieve / update / archive / delete

External code should call MemoryManager methods — not MemorySystem.save_memory()
directly when MEMORY_V2 is enabled.

V1 coexistence: conversation rows still written via V1 for full backward compatibility.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.modules.memory_classifier import MemoryClassifier
from backend.modules.memory_types import (
    ClassificationResult,
    MEMORY_TYPES,
    MemoryRecord,
    V1_CONVERSATION_TYPE,
)
from backend.modules.graph_manager import GraphManager
from backend.modules.retrieval_engine import RetrievalEngine

logger = logging.getLogger("memory.manager")


def memory_v2_enabled() -> bool:
    return os.getenv("MEMORY_V2_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class MemoryManager:
    """Cognitive memory façade."""

    def __init__(
        self,
        v1_memory_system,
        *,
        classifier: Optional[MemoryClassifier] = None,
        graph: Optional[GraphManager] = None,
        retrieval: Optional[RetrievalEngine] = None,
    ):
        self.v1 = v1_memory_system
        self.classifier = classifier or MemoryClassifier()
        uid = "default_user"
        self.graph = graph or GraphManager(
            redis_interface=getattr(v1_memory_system, "redis", None),
            user_id=uid,
        )
        self.retrieval = retrieval or RetrievalEngine(
            v1_memory_system, graph_manager=self.graph
        )

    @classmethod
    def from_clients(
        cls,
        supabase_client,
        openai_client,
        memories_table: str,
        redis_interface=None,
    ) -> "MemoryManager":
        from modules.memory_system import MemorySystem

        v1 = MemorySystem(
            supabase_client,
            openai_client,
            memories_table,
            redis_interface=redis_interface,
        )
        return cls(v1)

    # ------------------------------------------------------------------
    # Core V2 API
    # ------------------------------------------------------------------
    async def save(
        self,
        *,
        user_message: str,
        bot_response: str,
        conversation_id: str,
        user_id: str = "default_user",
        emotion: Optional[Dict[str, Any]] = None,
        reflection: Optional[Dict[str, Any]] = None,
        tool_result: Optional[Any] = None,
        document: Optional[str] = None,
        file_name: Optional[str] = None,
        ai_id: str = "xiaochenguang_v1",
        force_type: Optional[str] = None,
        skip_v1_conversation: bool = False,
    ) -> Dict[str, Any]:
        """
        Classify + persist.
        - Always keeps V1 conversation continuity unless skip_v1_conversation.
        - Additionally stores typed V2 row when type != pure passthrough.
        """
        conversation = {
            "user_message": user_message or "",
            "assistant_message": bot_response or "",
        }
        clf: ClassificationResult = self.classifier.classify(
            conversation=conversation,
            emotion=emotion,
            reflection=reflection,
            tool_result=tool_result,
            document=document,
        )
        if force_type and force_type in MEMORY_TYPES:
            clf.memory_type = force_type
            # forced typed writes (e.g. Night Growth) always persist
            clf.should_persist = True
            if not getattr(clf, "value_tier", None) or clf.value_tier == "low":
                clf.value_tier = "high"

        # ensure graph user scope
        self.graph.user_id = user_id or "default_user"

        v1_saved = False
        if not skip_v1_conversation:
            # V1 path for chat continuity (conversation memory_type)
            await self.v1.save_memory(
                conversation_id=conversation_id,
                user_input=user_message or "",
                bot_response=bot_response or "",
                emotion_analysis=emotion
                or {"dominant_emotion": "neutral", "intensity": 0.5},
                file_name=file_name,
                ai_id=ai_id,
                user_id=user_id,
                reflection=reflection,
            )
            v1_saved = True

        typed_id = None
        # Quality gate: only High/Medium (should_persist) write typed permanent rows.
        # Low-value chitchat keeps V1 continuity but skips permanent typed pollution.
        persist_typed = bool(force_type) or (
            clf.should_persist and clf.memory_type in MEMORY_TYPES
        )
        if persist_typed:
            typed_id = await self._insert_typed_record(
                memory_type=clf.memory_type,
                user_message=user_message or "",
                assistant_message=bot_response or "",
                conversation_id=conversation_id,
                user_id=user_id or "default_user",
                importance=clf.importance,
                confidence=clf.confidence,
                tags=clf.tags,
                ai_id=ai_id,
                meta={
                    "secondary_types": clf.secondary_types,
                    "relations": clf.relations,
                    "classification": clf.to_dict(),
                    "value_tier": getattr(clf, "value_tier", "medium"),
                },
            )
            if typed_id is not None:
                try:
                    self.graph.apply_classification_relations(
                        str(typed_id),
                        clf.relations,
                        related_memory_ids=[str(typed_id)],
                    )
                except Exception as e:
                    logger.warning("graph apply failed: %s", e)

        return {
            "ok": True,
            "v1_saved": v1_saved,
            "id": typed_id,
            "typed_persisted": bool(typed_id) and persist_typed,
            "value_tier": getattr(clf, "value_tier", "medium"),
            "memory_type": clf.memory_type,
            "importance": clf.importance,
            "confidence": clf.confidence,
            "tags": clf.tags,
            "classification": clf.to_dict(),
        }

    async def retrieve(
        self,
        query: str,
        *,
        conversation_id: str,
        user_id: str = "default_user",
        memory_types: Optional[List[str]] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        self.graph.user_id = user_id or "default_user"
        return await self.retrieval.retrieve(
            query,
            conversation_id=conversation_id,
            user_id=user_id,
            memory_types=memory_types,
            limit=limit,
        )

    async def update(
        self,
        memory_id: Any,
        *,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a typed or conversation row by id."""
        if not getattr(self.v1, "supabase", None):
            return {"ok": False, "error": "no_supabase"}
        table = self.v1.memories_table
        allowed = {
            "user_message",
            "assistant_message",
            "document_content",
            "importance_score",
            "memory_type",
            "access_count",
        }
        payload = {k: v for k, v in (fields or {}).items() if k in allowed}
        if not payload:
            return {"ok": False, "error": "no_valid_fields"}
        try:
            self.v1.supabase.table(table).update(payload).eq("id", memory_id).execute()
            return {"ok": True, "id": memory_id, "updated": payload}
        except Exception as e:
            logger.warning("update failed: %s", e)
            return {"ok": False, "error": str(e)}

    async def archive(self, memory_id: Any) -> Dict[str, Any]:
        """Soft-archive: mark document_content meta + lower importance; archive graph edges."""
        meta = json.dumps({"archived": True, "archived_at": datetime.utcnow().isoformat()})
        result = await self.update(
            memory_id,
            fields={
                "importance_score": 0.0,
                "document_content": f"[ARCHIVED] {meta}",
            },
        )
        try:
            if self.graph is not None:
                n = self.graph.archive_edges_for_memory(str(memory_id))
                result["graph_edges_archived"] = n
        except Exception as e:
            logger.warning("graph archive edges failed: %s", e)
        return result

    async def delete(self, memory_id: Any) -> Dict[str, Any]:
        if not getattr(self.v1, "supabase", None):
            return {"ok": False, "error": "no_supabase"}
        table = self.v1.memories_table
        try:
            self.v1.supabase.table(table).delete().eq("id", memory_id).execute()
            try:
                if self.graph is not None:
                    self.graph.remove_edges_for_memory(str(memory_id))
            except Exception as ge:
                logger.warning("graph remove edges failed: %s", ge)
            return {"ok": True, "id": memory_id, "deleted": True}
        except Exception as e:
            logger.warning("delete failed: %s", e)
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _insert_typed_record(
        self,
        *,
        memory_type: str,
        user_message: str,
        assistant_message: str,
        conversation_id: str,
        user_id: str,
        importance: float,
        confidence: float,
        tags: List[str],
        ai_id: str,
        meta: Dict[str, Any],
    ) -> Optional[Any]:
        if not getattr(self.v1, "supabase", None):
            return None
        # Skip empty
        if not (user_message or "").strip() and not (assistant_message or "").strip():
            return None
        table = self.v1.memories_table
        doc = {
            "v2": True,
            "confidence": confidence,
            "tags": tags,
            "meta": meta,
        }
        embedding_status = "pending"
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        text_blob = f"{user_message} {assistant_message}".strip()
        # Only attempt embedding when content is searchable
        searchable = bool(text_blob) and memory_type in MEMORY_TYPES

        data = {
            "conversation_id": conversation_id,
            "user_message": user_message[:4000],
            "assistant_message": assistant_message[:4000],
            "memory_type": memory_type,  # V2 type string
            "platform": "Web",
            "document_content": json.dumps(doc, ensure_ascii=False)[:8000],
            "created_at": datetime.now().isoformat(),
            "access_count": 1,
            "importance_score": float(importance),
            "ai_id": ai_id,
            "message_type": "memory_v2",
            "user_id": user_id,
        }
        # embedding — failure must not drop the row
        if searchable and getattr(self.v1, "openai_client", None):
            try:
                emb = self.v1.openai_client.embeddings.create(
                    model=embedding_model,
                    input=text_blob[:2000],
                )
                data["embedding"] = emb.data[0].embedding
                embedding_status = "ready"
            except Exception as e:
                logger.warning("v2 embedding failed (row still saved): %s", e)
                embedding_status = "failed"
        elif not searchable:
            embedding_status = "unavailable"
        else:
            embedding_status = "failed"

        doc["embedding_status"] = embedding_status
        doc["embedding_model"] = embedding_model if embedding_status == "ready" else None
        data["document_content"] = json.dumps(doc, ensure_ascii=False)[:8000]

        try:
            result = self.v1.supabase.table(table).insert(data).execute()
            if result.data:
                rid = result.data[0].get("id")
                # stash status on manager for tests/observability
                self._last_embedding_status = embedding_status
                return rid
            self._last_embedding_status = embedding_status
            return True
        except Exception as e:
            logger.warning("typed insert failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Legacy duck-type adapter for chat_router / kernel (Strangler)
    # ------------------------------------------------------------------
    def as_legacy(self) -> "LegacyMemoryAdapter":
        return LegacyMemoryAdapter(self)


class LegacyMemoryAdapter:
    """
    Drop-in surface compatible with MemorySystem methods used by chat_router:
      - save_memory
      - recall_memories
      - get_conversation_history
      - save_emotional_state
      - _cache_short_term (optional)
    """

    def __init__(self, manager: MemoryManager):
        self.manager = manager
        self.v1 = manager.v1
        # attributes some code may read
        self.supabase = getattr(self.v1, "supabase", None)
        self.openai_client = getattr(self.v1, "openai_client", None)
        self.memories_table = getattr(self.v1, "memories_table", None)
        self.redis = getattr(self.v1, "redis", None)
        self.emotion_detector = getattr(self.v1, "emotion_detector", None)

    async def save_memory(
        self,
        conversation_id: str,
        user_input: str,
        bot_response: str,
        emotion_analysis: dict,
        file_name: Optional[str] = None,
        ai_id: str = "xiaochenguang_v1",
        user_id: Optional[str] = None,
        reflection: Optional[Dict[str, Any]] = None,
    ):
        await self.manager.save(
            user_message=user_input,
            bot_response=bot_response,
            conversation_id=conversation_id,
            user_id=user_id or "default_user",
            emotion=emotion_analysis,
            reflection=reflection,
            file_name=file_name,
            ai_id=ai_id,
            skip_v1_conversation=False,
        )

    async def recall_memories(
        self,
        user_message: str,
        conversation_id: str,
        user_id: str = "default_user",
    ) -> str:
        result = await self.manager.retrieve(
            user_message,
            conversation_id=conversation_id,
            user_id=user_id,
            limit=5,
        )
        # Prefer formatted V2 block; fall back to V1-only text
        formatted = (result or {}).get("formatted") or ""
        if formatted:
            return formatted
        # extract v1 content if present
        for it in (result or {}).get("items") or []:
            if it.get("memory_type") == V1_CONVERSATION_TYPE:
                return it.get("content") or ""
        return ""

    def get_conversation_history(self, conversation_id: str, limit: int = 10):
        return self.v1.get_conversation_history(conversation_id, limit=limit)

    async def save_emotional_state(self, user_id: str, emotion_analysis: dict, context: str = ""):
        return await self.v1.save_emotional_state(user_id, emotion_analysis, context)

    def get_recent_context(self, conversation_id: str):
        return self.v1.get_recent_context(conversation_id)

    def _cache_short_term(self, *args, **kwargs):
        return self.v1._cache_short_term(*args, **kwargs)


def build_memory_backend(
    supabase_client,
    openai_client,
    memories_table: str,
    redis_interface=None,
):
    """
    Factory used by chat_router strangler:
      MEMORY_V2_ENABLED=true → LegacyMemoryAdapter(MemoryManager)
      else → MemorySystem V1
    """
    from modules.memory_system import MemorySystem

    v1 = MemorySystem(
        supabase_client,
        openai_client,
        memories_table,
        redis_interface=redis_interface,
    )
    if memory_v2_enabled():
        mgr = MemoryManager(v1)
        logger.info("Memory V2 enabled (Strangler adapter active)")
        return mgr.as_legacy()
    return v1
