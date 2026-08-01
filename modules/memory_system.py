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
import re
import hashlib
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


DEFAULT_CANDIDATE_POOL = 12
RANK_W_SIM = 0.6
RANK_W_OVERLAP = 0.4
# MMR relevance/diversity trade-off (0..1): higher favors relevance, lower favors
# diversity. Used so many distinct-but-topically-clustered distractors cannot take
# every slot even when each individually out-scores an older relevant memory.
RANK_MMR_LAMBDA = 0.7
# Fixed, bounded owner-scoped fallback scan. Independent of the candidate pool
# (which is clamped to 3..50); kept constant so a normal RPC with poor top
# candidates still admits older owner+AI-scoped memories into the candidate set.
FALLBACK_SCAN_BOUND = 50

# --- Opt-in de-identified recall diagnostics (default OFF) --------------------
# When MEMORY_RECALL_DIAGNOSTICS is truthy, recall emits ONE extra de-identified
# line listing the FINAL selected candidates (<= inject limit): a non-reversible
# 12-hex fingerprint + candidate source + rounded scores. It NEVER changes the
# candidate set, ranking, MMR, dedupe, tie-break, injected rows or their order,
# and NEVER logs raw messages, owner/ai/conversation ids, embeddings or secrets.
_DIAG_TRUTHY = {"1", "true", "yes", "on"}
_DIAG_UNIT_SEP = "\x1f"  # unit separator between user/assistant for the fingerprint


def _recall_diagnostics_enabled() -> bool:
    """Strict truthy parse; any error or missing value -> False (never raises)."""
    try:
        return str(os.getenv("MEMORY_RECALL_DIAGNOSTICS", "false")).strip().lower() in _DIAG_TRUTHY
    except Exception:
        return False


def _candidate_fingerprint(user_message, assistant_message) -> str:
    """Non-reversible short id for one-shot cross-referencing only.
    SHA-256(user + US + assistant)[:12] lowercase hex; not an identity/owner key."""
    try:
        raw = f"{user_message or ''}{_DIAG_UNIT_SEP}{assistant_message or ''}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:12]
    except Exception:
        return "000000000000"


def _diag_round(value) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return 0.0


def _candidate_pool() -> int:
    """Bounded semantic candidate pool size (separate from final injected count)."""
    try:
        v = int(os.getenv("MEMORY_CANDIDATE_POOL", str(DEFAULT_CANDIDATE_POOL)))
    except (TypeError, ValueError):
        v = DEFAULT_CANDIDATE_POOL
    return max(3, min(v, 50))


def _norm_for_match(text) -> str:
    """Normalize for Chinese-aware matching: lowercase, drop whitespace/punctuation.
    Char n-grams (not whitespace tokenization) are used so CJK rephrasings match."""
    s = str(text or "").lower()
    return re.sub(r"[\s\W_]+", "", s, flags=re.UNICODE)


def _char_ngrams(text, n: int = 2) -> set:
    s = _norm_for_match(text)
    if not s:
        return set()
    if len(s) < n:
        return {s}
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _overlap_score(query, text) -> float:
    """Fraction of query char-n-grams present in text (0..1). Chinese-friendly."""
    q = _char_ngrams(query)
    if not q:
        return 0.0
    t = _char_ngrams(text)
    if not t:
        return 0.0
    return len(q & t) / float(len(q))


def _ngram_jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return (len(a & b) / float(union)) if union else 0.0


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

    def _owner_scoped_conversation_rows(self, uid, aid, conversation_id, bound):
        """Bounded owner+AI-filtered conversation rows (recent). Legacy-null aware.
        A safe fallback candidate set merged into recall and reused by traditional_search."""
        legacy_default = (os.getenv("AI_ID", "xiaochenguang_v1") or "xiaochenguang_v1").strip()
        cols = "user_message, assistant_message, user_id, ai_id, conversation_id"
        # Respect MEMORY_SEMANTIC_SCOPE: in conversation_only mode the fallback (and
        # the traditional_search that reuses it) must NOT cross conversations.
        scope_to_conversation = (
            self.semantic_scope == "conversation_only" and bool(conversation_id)
        )

        def _fetch(legacy_null: bool):
            qq = (
                self.supabase.table(self.memories_table)
                .select(cols)
                .eq("memory_type", "conversation")
                .eq("user_id", uid)
            )
            qq = qq.is_("ai_id", "null") if legacy_null else qq.eq("ai_id", aid)
            if scope_to_conversation:
                qq = qq.eq("conversation_id", conversation_id)
            try:
                return qq.order("created_at", desc=True).limit(bound).execute().data or []
            except Exception:
                return []

        rows = list(_fetch(False))
        if aid == legacy_default:
            rows.extend(_fetch(True))
        # user strict + ai legacy-aware double-check (defense in depth)
        return [r for r in rows if r.get("user_id") == uid and _ai_match_legacy(r.get("ai_id"), aid)]

    def _rank_candidates(self, query, candidates, uid, aid, limit):
        """Hybrid re-rank + MMR diversify. Relevance = RPC cosine similarity + Chinese
        char-ngram overlap. Diversity is measured over the FULL memory content
        (user_message + assistant_message), not user_message alone, so that:
          - many distinct-but-topically-clustered distractors cannot occupy every slot
            even when each individually out-scores an older relevant memory, and
          - two memories that share a question but differ in answer are treated as
            distinct candidates (the answer-bearing one is never dropped as a near-dup).
        Exact-content duplicates are removed; owner+AI isolation is re-enforced.
        Returns up to `limit` rows. Recency is NOT a primary/dominant factor."""
        scored = []
        seen_exact = set()
        for cand in candidates:
            r = cand.get("row") or {}
            if r.get("user_id") != uid:                      # cross-owner guard
                continue
            if not _ai_match_legacy(r.get("ai_id"), aid):    # cross-AI guard (legacy-aware)
                continue
            um = r.get("user_message")
            am = r.get("assistant_message")
            if um is None and am is None:
                continue
            key = (_norm_for_match(um), _norm_for_match(am))
            if key in seen_exact:                            # exact-content dedupe
                continue
            seen_exact.add(key)
            content = f"{um or ''} {am or ''}"
            overlap = _overlap_score(query, content)
            sim = float(cand.get("sim") or 0.0)
            score = RANK_W_SIM * sim + RANK_W_OVERLAP * overlap
            # diversity signature over FULL content (never answer-blind)
            scored.append({
                "row": r, "score": score, "cg": _char_ngrams(content),
                "sim": sim, "overlap": overlap,
                "source": cand.get("source") or "unknown",
            })
        # Greedy MMR: each pick maximizes lambda*relevance - (1-lambda)*max_sim_to_chosen.
        remaining = list(scored)
        selected = []
        while remaining and len(selected) < limit:
            best = None
            best_mmr = None
            for cand in remaining:
                penalty = max(
                    (_ngram_jaccard(cand["cg"], sel["cg"]) for sel in selected),
                    default=0.0,
                )
                mmr = RANK_MMR_LAMBDA * cand["score"] - (1.0 - RANK_MMR_LAMBDA) * penalty
                if best_mmr is None or mmr > best_mmr:
                    best_mmr = mmr
                    best = cand
            best["mmr"] = best_mmr  # observability only; selection already decided
            selected.append(best)
            remaining.remove(best)
        try:
            print(f"\U0001f50e recall pool={len(candidates)} distinct={len(scored)} injected={len(selected)}")
        except Exception:
            pass
        # Opt-in de-identified diagnostics (default OFF). Never alters selection,
        # order or returned rows; failure here must not break recall/chat.
        if _recall_diagnostics_enabled():
            try:
                parts = []
                for i, sel in enumerate(selected, 1):
                    row = sel.get("row") or {}
                    fp = _candidate_fingerprint(row.get("user_message"), row.get("assistant_message"))
                    parts.append(
                        f"slot={i} fp={fp} src={sel.get('source', 'unknown')} "
                        f"cos={_diag_round(sel.get('sim'))} overlap={_diag_round(sel.get('overlap'))} "
                        f"rel={_diag_round(sel.get('score'))} mmr={_diag_round(sel.get('mmr'))}"
                    )
                print(f"\U0001f52c recall_diag injected={len(selected)} " + " | ".join(parts))
            except Exception:
                pass
        return [sel["row"] for sel in selected]

    async def search_relevant_memories(
        self,
        conversation_id: str,
        query: str,
        limit: int = 3,
        user_id: Optional[str] = None,
        ai_id: Optional[str] = None,
    ):
        """
        混合召回（Task 006 C6-F）：
        - 取較大的**有界候選池**（match_count = candidate pool，預設 12，上限 50），
          與最後注入 prompt 的筆數（limit，預設 3）分離。
        - 合併 current-conversation 與 same-user+same-AI 跨對話語意候選，**不短路**；
          並額外併入有界的 owner-scoped 候選（RPC 正常但候選品質不足時的安全 fallback，
          不因「有資料」而阻斷）。
        - 去重＋近似多樣化＋（cosine similarity + 中文字元 n-gram overlap）混合排序，
          最後只注入最多 `limit` 筆。
        - fail-closed：缺 user_id/ai_id 一律零結果；owner+AI 隔離與 0.55 安全底線不變。
        """
        uid = _owner_id(user_id)
        # strict fail-closed: the caller (recall_memories) already resolves the
        # default AI; an empty/None owner or ai_id here yields zero results.
        aid = _owner_id(ai_id)
        if not uid or not aid:
            print("\u26a0\ufe0f 搜尋記憶略過：缺少 user_id 或 ai_id（fail-closed）")
            return ""

        try:
            embedding_response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query,
            )
            query_embedding = embedding_response.data[0].embedding

            pool = _candidate_pool()
            scopes: list[Optional[str]] = []
            if conversation_id:
                scopes.append(conversation_id)
            if self.semantic_scope != "conversation_only":
                scopes.append(None)  # same user+ai cross-conversation
            seen_s = set()
            ordered_scopes = []
            for sc in scopes:
                kk = sc if sc is not None else ""
                if kk in seen_s:
                    continue
                seen_s.add(kk)
                ordered_scopes.append(sc)

            candidates = []
            # (1) semantic candidates from RPC — larger bounded pool, MERGE all scopes.
            for scope_conv in ordered_scopes:
                params = self._build_match_rpc_params(
                    query_embedding,
                    pool,
                    conversation_id=scope_conv,
                    user_id=uid,
                    ai_id=aid,
                )
                if not params:
                    return ""  # fail-closed
                try:
                    result = self.supabase.rpc(self.memory_rpc_name, params).execute()
                except Exception as rpc_err:
                    print(f"\u26a0\ufe0f 語意 RPC 失敗，改用 owner-scoped 傳統召回：{type(rpc_err).__name__}")
                    return await self.traditional_search(
                        conversation_id, query, limit, user_id=uid, ai_id=aid
                    )
                for r in (result.data or []):
                    candidates.append({"row": r, "sim": float(r.get("similarity") or 0.0), "source": "semantic"})

            # (2) owner-scoped fallback candidates (bounded) — always merged so a normal RPC
            #     with poor top candidates is not blocked from safe owner+AI-filtered recall.
            #     Uses a larger bounded scan so an older target still enters the candidate
            #     set even when higher-cosine near-duplicate distractors fill the RPC pool.
            for r in self._owner_scoped_conversation_rows(
                uid, aid, conversation_id, FALLBACK_SCAN_BOUND
            ):
                candidates.append({"row": r, "sim": 0.0, "source": "owner_fallback"})

            if not candidates:
                return ""

            ranked = self._rank_candidates(query, candidates, uid, aid, limit)
            return self._format_memory_rows(ranked)

        except Exception as e:
            print(f"\u274c 搜尋記憶失敗：{e}")
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
        """傳統文字降級（RPC 例外時）：owner+AI fail-closed；中文以字元 n-gram overlap
        比對（不依賴空白分詞）；有界 owner-scoped 查詢；去重後取最相關 limit 筆。"""
        uid = _owner_id(user_id)
        aid = _owner_id(ai_id)
        if not uid or not aid:
            return ""
        try:
            rows = self._owner_scoped_conversation_rows(uid, aid, conversation_id, max(limit * 4, 20))
            if not rows:
                return ""
            scored = []
            seen = set()
            for r in rows:
                if r.get("user_id") != uid or not _ai_match_legacy(r.get("ai_id"), aid):
                    continue
                um = r.get("user_message")
                am = r.get("assistant_message")
                key = (_norm_for_match(um), _norm_for_match(am))
                if key in seen:
                    continue
                seen.add(key)
                ov = _overlap_score(query, f"{um or ''} {am or ''}")
                if ov > 0:
                    scored.append((ov, r))
            scored.sort(key=lambda x: x[0], reverse=True)
            return self._format_memory_rows([r for _, r in scored[:limit]])
        except Exception as e:
            print(f"\u274c 傳統搜尋失敗：{e}")
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

            # Final cross-conversation recent fallback: only in cross-conversation
            # mode. In conversation_only mode this public entry must NOT pull memories
            # from other conversations (owner + AI isolation still applies either way).
            if not raw_memories and self.semantic_scope != "conversation_only":
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
