"""
統一記憶系統 — MemorySystem

唯一正式的對話記憶入口：
- 長期：Supabase（含 embedding 向量召回）
- 短期：Redis（conv:{id}:latest，可選降級 Mock）

Task 006 contract_version: task006_v1
- Semantic recall prefers match_memories_v2 (user_id/ai_id isolation)
- Emotion writes use new-schema canonical fields
"""
import os
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from modules.emotion_detector import EnhancedEmotionDetector

CONTRACT_VERSION = "task006_v1"
# Conservative cosine floor; calibrate with real samples at Gate C.
DEFAULT_MIN_SIMILARITY = 0.55


def _owner_id(value: Optional[str]) -> Optional[str]:
    """Fail-closed owner: empty → None (caller must not query). 'default_user' is a real owner key."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _ai_match_legacy(row_ai: Any, requested_ai: Optional[str]) -> bool:
    """AI-owner match with legacy-NULL compatibility (PR18 review round 2).

    - Explicit row ai_id must equal the requested ai_id (no cross-AI leak).
    - A legacy row without ai_id belongs to the historical/default AI only, so
      it is returned ONLY when the requested ai is that legacy default.
    user_id isolation is enforced strictly by the caller.
    """
    ra = str(row_ai).strip() if row_ai is not None else ""
    req = str(requested_ai or "").strip()
    if not ra:
        legacy_default = (os.getenv("AI_ID", "xiaochenguang_v1") or "xiaochenguang_v1").strip()
        return bool(req) and req == legacy_default
    return ra == req


class MemorySystem:
    def __init__(
        self,
        supabase_client,
        openai_client,
        memories_table: str,
        redis_interface=None,
    ):
        self.supabase = supabase_client
        self.openai_client = openai_client
        self.memories_table = memories_table
        self.emotion_detector = EnhancedEmotionDetector()
        self.redis = redis_interface
        # Only match_memories_v2 is supported for app paths (legacy RPC raises).
        self.memory_rpc_name = (
            os.getenv("MEMORY_RPC_NAME", "match_memories_v2").strip() or "match_memories_v2"
        )
        # user_ai_cross_conversation (default) | conversation_only
        self.semantic_scope = (
            os.getenv("MEMORY_SEMANTIC_SCOPE", "user_ai_cross_conversation").strip()
            or "user_ai_cross_conversation"
        )
        if self.redis is None:
            try:
                from backend.redis_interface import get_shared_redis_interface
                self.redis = get_shared_redis_interface()
            except Exception as e:
                print(f"⚠️ Redis 初始化略過（不影響長期記憶）: {e}")
                self.redis = None

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
        """儲存對話到 Supabase（長期）與 Redis（短期快取）"""
        try:
            # 空回覆或錯誤回覆不得寫入長期記憶
            bot_text = (bot_response or "").strip()
            if not bot_text or bot_text.startswith("[ERROR]"):
                print(
                    f"⚠️ 略過記憶儲存：空回覆或錯誤回覆 "
                    f"conv={(conversation_id or '')[:8]}..."
                )
                return

            length_score = (len(user_input) // 20) * 0.1
            keyword_score = sum(
                1 for keyword in self.emotion_detector.emotion_dictionary.keys()
                for k in self.emotion_detector.emotion_dictionary[keyword]["keywords"]
                if k.lower() in user_input.lower()
            ) * 0.3
            intensity_score = emotion_analysis.get("intensity", 0.5)
            importance_score = length_score + keyword_score + intensity_score

            embedding_response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=f"{user_input} {bot_response}"
            )
            embedding = embedding_response.data[0].embedding

            existing = self.supabase.table(self.memories_table)\
                .select("id", "access_count")\
                .eq("conversation_id", conversation_id)\
                .eq("user_message", user_input)\
                .eq("memory_type", "conversation")\
                .execute()

            access_count = existing.data[0]["access_count"] + 1 if existing.data else 1

            data = {
                "conversation_id": conversation_id,
                "user_message": user_input,
                "assistant_message": bot_response,
                "embedding": embedding,
                "memory_type": "conversation",
                "platform": "Web",
                "document_content": f"對話記錄: {user_input} -> {bot_response}",
                "created_at": datetime.now().isoformat(),
                "access_count": access_count,
                "importance_score": importance_score,
                "file_name": file_name,
                "ai_id": ai_id,
                "message_type": "text",
            }
            if user_id:
                data["user_id"] = user_id

            if existing.data:
                self.supabase.table(self.memories_table)\
                    .update(data)\
                    .eq("id", existing.data[0]["id"])\
                    .execute()
            else:
                self.supabase.table(self.memories_table).insert(data).execute()

            # 短期快取：最新一輪對話（含可選反思）
            self._cache_short_term(
                conversation_id=conversation_id,
                user_id=user_id,
                user_input=user_input,
                bot_response=bot_response,
                reflection=reflection,
            )

            print(
                f"✅ 記憶已儲存 - conv={conversation_id[:8]}..., "
                f"access_count={access_count}, importance={importance_score:.2f}"
            )

        except Exception as e:
            print(f"❌ 儲存記憶失敗：{e}")

    def _cache_short_term(
        self,
        conversation_id: str,
        user_id: Optional[str],
        user_input: str,
        bot_response: str,
        reflection: Optional[Dict[str, Any]] = None,
    ):
        """寫入 Redis 短期記憶（失敗不影響主流程）— 標準 key: conv:{id}:latest"""
        if not self.redis:
            return
        try:
            from datetime import timezone as _tz

            try:
                from backend.modules.reflection_contract import normalize_reflection

                refl = normalize_reflection(reflection) if reflection is not None else None
            except Exception:
                refl = reflection

            now = datetime.now(_tz.utc).isoformat()
            payload = {
                "messages": [
                    {"role": "user", "content": user_input or ""},
                    {"role": "assistant", "content": bot_response or ""},
                ],
                "summary": (bot_response or user_input or "")[:200],
                "reflection": refl,
                "updated_at": now,
                "user_id": user_id,
                # legacy mirrors retained for older readers
                "user_msg": user_input,
                "assistant_msg": bot_response,
                "timestamp": now,
            }
            self.redis.store_short_term(conversation_id, payload)
        except Exception as e:
            print(f"⚠️ Redis 短期記憶寫入失敗（已略過）: {e}")

    def get_recent_context(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """從 Redis 讀取最近一輪對話上下文"""
        if not self.redis:
            return None
        try:
            return self.redis.load_recent_context(conversation_id)
        except Exception as e:
            print(f"⚠️ 讀取 Redis 上下文失敗: {e}")
            return None

    def get_conversation_history(self, conversation_id: str, limit: int = 10):
        """獲取對話歷史（Supabase）"""
        try:
            result = self.supabase.table(self.memories_table)\
                .select("user_message, assistant_message, created_at")\
                .eq("conversation_id", conversation_id)\
                .eq("memory_type", "conversation")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()

            if result.data:
                history = []
                for msg in reversed(result.data):
                    history.append(f"用戶: {msg['user_message']}")
                    history.append(f"小宸光: {msg['assistant_message']}")
                return "\n".join(history)
            return ""

        except Exception as e:
            print(f"❌ 獲取歷史失敗：{e}")
            return ""

    def _min_similarity(self) -> float:
        try:
            return float(os.getenv("MEMORY_MIN_SIMILARITY", str(DEFAULT_MIN_SIMILARITY)))
        except (TypeError, ValueError):
            return DEFAULT_MIN_SIMILARITY

    def _build_match_rpc_params(
        self,
        query_embedding,
        limit: int,
        *,
        conversation_id: Optional[str],
        user_id: Optional[str],
        ai_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Build match_memories_v2 params. None if owner filters incomplete (fail-closed)."""
        uid = _owner_id(user_id)
        aid = _owner_id(ai_id)
        if not uid or not aid:
            return None
        return {
            "query_embedding": query_embedding,
            "match_count": limit,
            "filter_conversation_id": conversation_id or None,
            "filter_user_id": uid,
            "filter_ai_id": aid,
            "min_similarity": self._min_similarity(),
        }

    def _format_memory_rows(self, rows) -> str:
        memories = []
        for memory in rows or []:
            um = memory.get("user_message")
            am = memory.get("assistant_message")
            if um is None and am is None:
                continue
            memories.append(f"相關記憶: {um} -> {am}")
        return "\n".join(memories)

    async def search_relevant_memories(
        self,
        conversation_id: str,
        query: str,
        limit: int = 3,
        user_id: Optional[str] = None,
        ai_id: Optional[str] = None,
    ):
        """
        向量相似度搜尋。
        Scope: same user_id + ai_id (cross-conversation by default).
        Prefer current conversation first, then expand across conversations.
        Fail-closed when user_id/ai_id missing.
        """
        uid = _owner_id(user_id)
        aid = _owner_id(ai_id) or _owner_id(os.getenv("AI_ID", "xiaochenguang_v1"))
        if not uid or not aid:
            print("⚠️ 搜尋記憶略過：缺少 user_id 或 ai_id（fail-closed）")
            return ""

        try:
            embedding_response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_embedding = embedding_response.data[0].embedding

            # 1) conversation-scoped (if provided)
            scopes: list[Optional[str]] = []
            if conversation_id:
                scopes.append(conversation_id)
            if self.semantic_scope != "conversation_only":
                scopes.append(None)  # cross-conversation long-term
            # dedupe while preserving order
            seen = set()
            ordered_scopes = []
            for s in scopes:
                key = s if s is not None else ""
                if key in seen:
                    continue
                seen.add(key)
                ordered_scopes.append(s)

            for scope_conv in ordered_scopes:
                params = self._build_match_rpc_params(
                    query_embedding,
                    limit,
                    conversation_id=scope_conv,
                    user_id=uid,
                    ai_id=aid,
                )
                if not params:
                    return ""
                result = self.supabase.rpc("match_memories_v2", params).execute()
                if result.data:
                    return self._format_memory_rows(result.data)
            return ""

        except Exception as e:
            print(f"❌ 搜尋記憶失敗：{e}")
            return await self.traditional_search(
                conversation_id, query, limit, user_id=uid, ai_id=aid
            )

    async def traditional_search(
        self,
        conversation_id: str,
        query: str,
        limit: int = 3,
        user_id: Optional[str] = None,
        ai_id: Optional[str] = None,
    ):
        """傳統文字搜尋：fail-closed owner；可跨 conversation（同 user+ai）"""
        uid = _owner_id(user_id)
        aid = _owner_id(ai_id)
        if not uid or not aid:
            return ""
        try:
            # DB-level ai filtering to avoid cross-AI query-limit starvation
            # (PR18 review round 3): explicit ai in SQL; legacy NULL fetched via a
            # SECOND bounded query only for the legacy default AI. user_id strict.
            select_cols = "user_message, assistant_message, user_id, ai_id, conversation_id"
            legacy_default = (os.getenv("AI_ID", "xiaochenguang_v1") or "xiaochenguang_v1").strip()

            def _fetch(legacy_null: bool):
                qq = (
                    self.supabase.table(self.memories_table)
                    .select(select_cols)
                    .eq("memory_type", "conversation")
                    .eq("user_id", uid)
                )
                if legacy_null:
                    qq = qq.is_("ai_id", "null")
                else:
                    qq = qq.eq("ai_id", aid)
                if self.semantic_scope == "conversation_only" and conversation_id:
                    qq = qq.eq("conversation_id", conversation_id)
                return qq.limit(limit * 4).execute().data or []

            rows = list(_fetch(False))
            if aid == legacy_default:
                rows.extend(_fetch(True))

            if rows:
                relevant = []
                query_words = query.lower().split()
                # Prefer same-conversation hits first
                if conversation_id:
                    rows.sort(
                        key=lambda r: 0 if r.get("conversation_id") == conversation_id else 1
                    )
                for memory in rows:
                    # user strict; ai legacy-aware double-check
                    if memory.get("user_id") != uid:
                        continue
                    if not _ai_match_legacy(memory.get("ai_id"), aid):
                        continue
                    user_msg = (memory.get("user_message") or "").lower()
                    if any(word in user_msg for word in query_words):
                        relevant.append(
                            f"相關記憶: {memory['user_message']} -> {memory['assistant_message']}"
                        )
                        if len(relevant) >= limit:
                            break
                return "\n".join(relevant)
            return ""
        except Exception as e:
            print(f"❌ 傳統搜尋失敗：{e}")
            return ""

    async def recall_memories(
        self,
        user_message: str,
        conversation_id: str,
        user_id: str = "default_user",
        ai_id: Optional[str] = None,
    ) -> str:
        """召回：語意（user+ai 跨對話）→ 近期同對話 → 近期同 user+ai。fail-closed。"""
        uid = _owner_id(user_id)
        aid = _owner_id(ai_id) or _owner_id(os.getenv("AI_ID", "xiaochenguang_v1"))
        if not uid or not aid:
            print("⚠️ 記憶召回略過：缺少 user_id 或 ai_id（fail-closed）")
            return ""
        try:
            raw_memories = await self.search_relevant_memories(
                conversation_id,
                user_message,
                limit=3,
                user_id=uid,
                ai_id=aid,
            )

            if not raw_memories and conversation_id:
                q = (
                    self.supabase.table(self.memories_table)
                    .select("user_message, assistant_message")
                    .eq("conversation_id", conversation_id)
                    .eq("memory_type", "conversation")
                    .eq("user_id", uid)
                    .eq("ai_id", aid)
                )
                recent_result = q.order("created_at", desc=True).limit(5).execute()
                if recent_result.data:
                    raw_memories = "\n".join([
                        f"相關記憶: {m['user_message']} -> {m['assistant_message']}"
                        for m in recent_result.data
                    ])

            if not raw_memories:
                q = (
                    self.supabase.table(self.memories_table)
                    .select("user_message, assistant_message")
                    .eq("user_id", uid)
                    .eq("ai_id", aid)
                    .eq("memory_type", "conversation")
                )
                cross_result = q.order("created_at", desc=True).limit(5).execute()
                if cross_result.data:
                    raw_memories = "\n".join([
                        f"相關記憶: {m['user_message']} -> {m['assistant_message']}"
                        for m in cross_result.data
                    ])

            if not raw_memories:
                return ""

            memory_lines = raw_memories.split("\n")
            formatted_memories = ["【喚醒記憶】"]
            for line in memory_lines:
                if line.startswith("相關記憶:"):
                    parts = line.replace("相關記憶: ", "").split(" -> ")
                    if len(parts) == 2:
                        user_msg, assistant_msg = parts
                        formatted_memories.append(f"- 你曾對我說：「{user_msg}」")
                        formatted_memories.append(f"- 我當時回應你：「{assistant_msg}」")

            return "\n".join(formatted_memories) if len(formatted_memories) > 1 else ""

        except Exception as e:
            print(f"❌ 記憶召回失敗：{e}")
            return ""

    async def save_emotional_state(self, user_id: str, emotion_analysis: dict, context: str = ""):
        """儲存情緒狀態到 emotional_states（Task006 新表正式欄位）"""
        try:
            intensity = float(emotion_analysis.get("intensity", 0.5) or 0.5)
            confidence = float(emotion_analysis.get("confidence", 0.0) or 0.0)
            intensity = max(0.0, min(1.0, intensity))
            confidence = max(0.0, min(1.0, confidence))
            data = {
                "user_id": user_id,
                "dominant_emotion": emotion_analysis.get("dominant_emotion") or "neutral",
                "intensity": intensity,
                "confidence": confidence,
                "context": context or "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            self.supabase.table("emotional_states").insert(data).execute()
            print(f"✅ 情緒狀態已儲存 - 用戶: {(user_id or '')[:8]}...")
            return {"permanent_store": "success", "contract_version": CONTRACT_VERSION}

        except Exception as e:
            print(f"❌ 儲存情緒狀態失敗：{e}")
            return {
                "permanent_store": "failed",
                "contract_version": CONTRACT_VERSION,
                "error_category": type(e).__name__,
            }
