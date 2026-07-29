"""Task 006 — data contract unit/isolation tests (mocked + SQL file checks)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.memory_system import MemorySystem, CONTRACT_VERSION as MEM_CV
from backend.modules.memory_manager import MemoryManager
from backend.modules.reflection_storage import ReflectionStorage, CONTRACT_VERSION as REF_CV
from backend.modules.pinecone_handler import PineconeHandler
from tests.mocks.mock_openai import FakeOpenAIClient
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_redis import MockRedisInterface

ROOT = Path(__file__).resolve().parents[2]
FWD = ROOT / "supabase" / "migrations" / "20260728_task006_core_data_contracts_forward.sql"
RBACK = ROOT / "supabase" / "migrations" / "20260728_task006_core_data_contracts_rollback.sql"

# Non-null embedding required by match_memories_v2 (WHERE embedding IS NOT NULL)
EMB = [0.1, 0.2, 0.3]


@pytest.fixture
def mem_env():
    sb = MockSupabase()
    openai = FakeOpenAIClient()
    redis = MockRedisInterface()
    ms = MemorySystem(sb, openai, "xiaochenguang_memories", redis_interface=redis)
    return ms, sb, openai, redis


@pytest.mark.unit
def test_migration_files_exist_and_idempotent_markers():
    assert FWD.is_file()
    assert RBACK.is_file()
    text = FWD.read_text(encoding="utf-8")
    assert "match_memories_v2" in text
    assert "filter_user_id" in text
    assert "filter_ai_id" in text
    assert "ADD COLUMN IF NOT EXISTS" in text
    assert "CREATE TABLE IF NOT EXISTS public.user_preferences" in text
    assert "confidence_score" in text
    assert "reflection_key" in text
    assert "<=>" in text  # cosine distance
    assert "<#>" not in text  # do not reuse old inner-product formula for v2 body
    rb = RBACK.read_text(encoding="utf-8")
    assert "DROP FUNCTION IF EXISTS public.match_memories_v2" in rb


@pytest.mark.unit
@pytest.mark.asyncio
async def test_emotion_write_uses_canonical_new_schema_fields(mem_env):
    ms, sb, *_ = mem_env
    result = await ms.save_emotional_state(
        "user-a",
        {"dominant_emotion": "joy", "intensity": 0.8, "confidence": 0.7},
        context="開心",
    )
    assert result["permanent_store"] == "success"
    rows = sb.table("emotional_states").rows
    assert len(rows) == 1
    row = rows[0]
    assert row["dominant_emotion"] == "joy"
    assert "emotion_type" not in row
    assert "timestamp" not in row
    assert "created_at" in row
    assert 0.0 <= row["intensity"] <= 1.0
    assert 0.0 <= row["confidence"] <= 1.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_rpc_v2_user_isolation(mem_env):
    ms, sb, openai, _ = mem_env
    # seed two users same conversation id (collision scenario)
    sb.table("xiaochenguang_memories").rows.extend(
        [
            {
                "conversation_id": "shared-conv",
                "user_id": "user-a",
                "ai_id": "xiaochenguang_v1",
                "user_message": "我是 A 的秘密",
                "assistant_message": "好的 A",
                "memory_type": "conversation",
                "embedding": EMB,
            },
            {
                "conversation_id": "shared-conv",
                "user_id": "user-b",
                "ai_id": "xiaochenguang_v1",
                "user_message": "我是 B 的秘密",
                "assistant_message": "好的 B",
                "memory_type": "conversation",
                "embedding": EMB,
            },
        ]
    )
    os.environ["MEMORY_RPC_NAME"] = "match_memories_v2"
    ms.memory_rpc_name = "match_memories_v2"
    out = await ms.search_relevant_memories(
        "shared-conv", "秘密", limit=5, user_id="user-a", ai_id="xiaochenguang_v1"
    )
    assert "我是 A 的秘密" in out
    assert "我是 B 的秘密" not in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_rpc_v2_ai_isolation(mem_env):
    ms, sb, *_ = mem_env
    sb.table("xiaochenguang_memories").rows.extend(
        [
            {
                "conversation_id": "c1",
                "user_id": "user-a",
                "ai_id": "xiaochenguang_v1",
                "user_message": "光光記憶",
                "assistant_message": "ok",
                "memory_type": "conversation",
                "embedding": EMB,
            },
            {
                "conversation_id": "c1",
                "user_id": "user-a",
                "ai_id": "story_master_v1",
                "user_message": "故事記憶",
                "assistant_message": "ok",
                "memory_type": "conversation",
                "embedding": EMB,
            },
        ]
    )
    ms.memory_rpc_name = "match_memories_v2"
    out = await ms.search_relevant_memories(
        "c1", "記憶", limit=5, user_id="user-a", ai_id="xiaochenguang_v1"
    )
    assert "光光記憶" in out
    assert "故事記憶" not in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reflection_durable_requires_supabase_not_redis_only():
    sb = MockSupabase()
    redis = MockRedisInterface()
    # Ensure redis.redis exists for list ops
    if not hasattr(redis, "redis") or redis.redis is None:
        redis.redis = MagicMock()
        redis.redis.lpush = MagicMock()
        redis.redis.ltrim = MagicMock()
        redis.redis.expire = MagicMock()

    storage = ReflectionStorage(redis_interface=redis, supabase_client=None, pinecone_handler=None)
    result = await storage.store_reflection(
        {"summary": "test", "causes": [], "lessons": [], "confidence": 0.5},
        conversation_id="c1",
        user_id="user-a",
    )
    # Without supabase, durable must not claim success
    assert result["permanent_store"] in ("skipped", "failed")
    assert result["durable_success"] is False
    assert result["overall_success"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reflection_supabase_write_omits_bigint_id_and_sets_key():
    sb = MockSupabase()
    storage = ReflectionStorage(redis_interface=None, supabase_client=sb, pinecone_handler=None)
    result = await storage.store_reflection(
        {"summary": "lesson", "causes": ["c"], "lessons": ["l"], "confidence": 0.9},
        conversation_id="c1",
        user_id="user-a",
        ai_id="xiaochenguang_v1",
    )
    assert result["permanent_store"] == "success"
    assert result["durable_success"] is True
    rows = sb.table("xiaochenguang_reflections").rows
    assert len(rows) == 1
    row = rows[0]
    # Mock may add auto id, but runtime must provide reflection_key and confidence_score
    assert "reflection_key" in row
    assert row["confidence_score"] == 0.9
    assert row.get("conversation_id") == "c1"
    # The insert payload from ReflectionStorage should not force a UUID into id
    # (mock may assign int id via next_id)
    assert isinstance(row.get("id"), int) or row.get("id") is None or row.get("id") != row["reflection_key"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_latest_reflection_singular_alias():
    sb = MockSupabase()
    storage = ReflectionStorage(supabase_client=sb)
    await storage.store_reflection(
        {"summary": "one", "confidence": 0.4},
        conversation_id="cx",
        user_id="u1",
        ai_id="xiaochenguang_v1",
    )
    latest = await storage.get_latest_reflection(
        conversation_id="cx", user_id="u1", ai_id="xiaochenguang_v1"
    )
    assert latest is not None
    # Real assertion (no `or True`): the stored summary must round-trip.
    assert latest.get("reflection_content") == "one"
    # row content persisted with owner
    rows = sb.table("xiaochenguang_reflections").rows
    assert rows and rows[0].get("user_id") == "u1"
    assert rows[0].get("ai_id") == "xiaochenguang_v1"


@pytest.mark.unit
def test_pinecone_adapter_methods_exist():
    ph = PineconeHandler.__new__(PineconeHandler)
    ph.enabled = False
    ph.index = None
    assert hasattr(ph, "store_reflection_with_text")
    assert hasattr(ph, "query_similar_reflections")
    assert ph.store_reflection_with_text("k", "text", {}) is False
    assert ph.query_similar_reflections(query_text="x") == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_preferences_table_contract_insert():
    """Call-site shape for user_preferences (table created by migration)."""
    sb = MockSupabase()
    payload = {
        "user_id": "user-a",
        "personality_profile": ["溫柔體貼"],
        "voice_settings": {"voice": "alloy"},
    }
    sb.table("user_preferences").insert(payload).execute()
    rows = sb.table("user_preferences").rows
    assert rows[0]["user_id"] == "user-a"
    assert "personality_profile" in rows[0]
    assert "voice_settings" in rows[0]


@pytest.mark.unit
def test_contract_versions_aligned():
    assert MEM_CV == "task006_v1"
    assert REF_CV == "task006_v1"


@pytest.mark.unit
def test_forward_sql_has_no_drop_column_on_emotion():
    text = FWD.read_text(encoding="utf-8")
    # additive only — no DROP COLUMN
    assert "DROP COLUMN" not in text.upper().replace(" ", "") or "DROP COLUMN" not in text
    assert not re.search(r"\bDROP\s+COLUMN\b", text, re.I)


# ===========================================================================
# PR18 review regressions (P0-1, P0-2, P0-3, P1-1, P1-3)
# ===========================================================================


class _SpyRetrieval:
    """Captures the kwargs passed down the real V2 chain."""

    def __init__(self):
        self.captured = {}

    async def retrieve(self, query, *, conversation_id, user_id="default_user",
                       memory_types=None, limit=5, ai_id=None):
        self.captured = {
            "query": query,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "ai_id": ai_id,
            "limit": limit,
        }
        return {"formatted": f"ok:{ai_id}", "items": []}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adapter_path_forwards_ai_id_end_to_end():
    """P0-1: chat_router → LegacyMemoryAdapter → MemoryManager → RetrievalEngine
    must carry ai_id. Proven with a spy retrieval engine on the real manager."""
    from types import SimpleNamespace

    spy = _SpyRetrieval()
    v1 = MagicMock()
    mgr = MemoryManager(
        v1,
        classifier=MagicMock(),
        graph=SimpleNamespace(user_id=None),
        retrieval=spy,
    )
    adapter = mgr.as_legacy()
    out = await adapter.recall_memories(
        "查詢", "conv-1", user_id="user-a", ai_id="story_master_v1"
    )
    assert spy.captured["ai_id"] == "story_master_v1"
    assert spy.captured["user_id"] == "user-a"
    assert spy.captured["conversation_id"] == "conv-1"
    assert "story_master_v1" in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_v2_default_user_is_real_owner_not_bypass(mem_env):
    """P0-2: default_user must be a real owner key, NOT a filter bypass."""
    ms, sb, *_ = mem_env
    sb.table("xiaochenguang_memories").rows.extend(
        [
            {
                "conversation_id": "cshared",
                "user_id": "default_user",
                "ai_id": "xiaochenguang_v1",
                "user_message": "預設使用者記憶",
                "assistant_message": "ok",
                "memory_type": "conversation",
                "embedding": EMB,
            },
            {
                "conversation_id": "cshared",
                "user_id": "real-user",
                "ai_id": "xiaochenguang_v1",
                "user_message": "真實使用者機密",
                "assistant_message": "ok",
                "memory_type": "conversation",
                "embedding": EMB,
            },
        ]
    )
    ms.memory_rpc_name = "match_memories_v2"
    out = await ms.search_relevant_memories(
        "cshared", "記憶", limit=5, user_id="default_user", ai_id="xiaochenguang_v1"
    )
    assert "預設使用者記憶" in out
    assert "真實使用者機密" not in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_v2_fail_closed_when_owner_missing(mem_env):
    """P0-2: missing user_id must fail closed (empty), never return all rows."""
    ms, sb, *_ = mem_env
    sb.table("xiaochenguang_memories").rows.append(
        {
            "conversation_id": "c",
            "user_id": "user-a",
            "ai_id": "xiaochenguang_v1",
            "user_message": "秘密",
            "assistant_message": "ok",
            "memory_type": "conversation",
            "embedding": EMB,
        }
    )
    ms.memory_rpc_name = "match_memories_v2"
    out = await ms.search_relevant_memories(
        "c", "秘密", limit=5, user_id=None, ai_id="xiaochenguang_v1"
    )
    assert out == ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reflection_read_isolated_by_user_and_ai():
    """P1-1: reflection reads must isolate user_id + ai_id (Supabase path)."""
    sb = MockSupabase()
    storage = ReflectionStorage(supabase_client=sb)
    await storage.store_reflection(
        {"summary": "光光的反思", "confidence": 0.6},
        conversation_id="c", user_id="u1", ai_id="xiaochenguang_v1",
    )
    await storage.store_reflection(
        {"summary": "故事大師的反思", "confidence": 0.6},
        conversation_id="c", user_id="u1", ai_id="story_master_v1",
    )
    got = await storage.get_latest_reflections(
        "c", limit=5, user_id="u1", ai_id="xiaochenguang_v1"
    )
    assert got
    assert all(r.get("ai_id") == "xiaochenguang_v1" for r in got)
    assert all(r.get("reflection_content") != "故事大師的反思" for r in got)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reflection_redis_rejects_legacy_record_missing_owner():
    """P1-1: with an owner filter, cache records lacking owner must be rejected."""
    import json as _json

    class _Conn:
        def __init__(self, items):
            self._items = items

        def lrange(self, key, a, b):
            return self._items

    class _Redis:
        def __init__(self, items):
            self.redis = _Conn(items)

    items = [
        _json.dumps({"user_id": "u1", "ai_id": "xiaochenguang_v1", "reflection_content": "keep"}),
        _json.dumps({"reflection_content": "legacy_no_owner"}),  # missing user_id AND ai_id
        _json.dumps({"user_id": "u1", "reflection_content": "has_user_no_ai"}),  # missing ai_id only
        _json.dumps({"user_id": "other", "ai_id": "xiaochenguang_v1", "reflection_content": "other_user"}),
    ]
    storage = ReflectionStorage(redis_interface=_Redis(items))
    got = await storage.get_latest_reflections(
        "c", limit=5, user_id="u1", ai_id="xiaochenguang_v1"
    )
    contents = [r["reflection_content"] for r in got]
    assert contents == ["keep"]
    # explicitly: a record with user_id but NO ai_id must be rejected (not auto-filled)
    assert "has_user_no_ai" not in contents
    assert "legacy_no_owner" not in contents
    assert "other_user" not in contents


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reflection_vector_search_requires_and_filters_owner():
    """P1-1: Pinecone reflection search must filter user_id + ai_id and fail closed."""
    class _FakePinecone:
        enabled = True

        def __init__(self):
            self.captured_filter = "unset"

        def generate_embedding(self, text):
            return [0.1, 0.2, 0.3]

        def query_similar_reflections(self, query_embedding=None, top_k=5,
                                      filter_metadata=None, query_text=None):
            self.captured_filter = filter_metadata
            return [{"id": "x"}]

    fp = _FakePinecone()
    storage = ReflectionStorage(pinecone_handler=fp)
    res = await storage.search_similar_reflections("q", user_id="u1", ai_id="story_master_v1")
    assert res
    assert fp.captured_filter == {"user_id": "u1", "ai_id": "story_master_v1"}

    # fail-closed: missing user_id → empty, and Pinecone not queried
    fp2 = _FakePinecone()
    storage2 = ReflectionStorage(pinecone_handler=fp2)
    res2 = await storage2.search_similar_reflections("q", user_id=None, ai_id="story_master_v1")
    assert res2 == []
    assert fp2.captured_filter == "unset"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pinecone_vector_store_status_paths():
    """P1-3: distinguish disabled / success / failed vector_store honestly."""
    class _Pc:
        def __init__(self, mode):
            self.enabled = True
            self.mode = mode

        def store_reflection_with_text(self, reflection_id, reflection_text, metadata):
            if self.mode == "success":
                return True
            if self.mode == "fail":
                return False
            raise RuntimeError("boom")

    base = {"summary": "s", "confidence": 0.5}

    # disabled (no handler)
    r_disabled = await ReflectionStorage().store_reflection(base, conversation_id="c", user_id="u1")
    assert r_disabled["vector_store"] == "disabled"

    # success
    r_ok = await ReflectionStorage(pinecone_handler=_Pc("success")).store_reflection(
        base, conversation_id="c", user_id="u1"
    )
    assert r_ok["vector_store"] == "success"

    # failure (exception path)
    r_fail = await ReflectionStorage(pinecone_handler=_Pc("raise")).store_reflection(
        base, conversation_id="c", user_id="u1"
    )
    assert r_fail["vector_store"] == "failed"


@pytest.mark.unit
def test_user_preferences_call_site_read_isolated_by_user():
    """P1-3: mirror personality_engine call site (select personality_profile eq user_id)."""
    sb = MockSupabase()
    sb.table("user_preferences").insert(
        {"user_id": "user-a", "personality_profile": ["溫柔體貼"], "voice_settings": {"voice": "alloy"}}
    ).execute()
    sb.table("user_preferences").insert(
        {"user_id": "user-b", "personality_profile": ["活潑開朗"]}
    ).execute()

    res = (
        sb.table("user_preferences")
        .select("personality_profile")
        .eq("user_id", "user-a")
        .limit(1)
        .execute()
    )
    assert res.data
    assert res.data[0]["personality_profile"] == ["溫柔體貼"]
    # isolation: user-b's traits never returned by user-a's query
    assert all(r["personality_profile"] != ["活潑開朗"] for r in res.data)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieval_legacy_null_ai_visible_to_default_not_other(mem_env):
    """Round 2 P0/migration: legacy rows with NULL ai_id stay retrievable for the
    legacy default AI, but are NEVER leaked to a different explicit AI. user_id strict."""
    from backend.modules.retrieval_engine import RetrievalEngine

    ms, sb, *_ = mem_env
    sb.table("xiaochenguang_memories").rows.extend(
        [
            {   # legacy row: no ai_id at all
                "id": "leg",
                "user_id": "u1",
                "user_message": "沒有ai欄位的舊記憶",
                "assistant_message": "ok",
                "memory_type": "semantic",
                "importance_score": 0.8,
                "embedding": EMB,
            },
            {   # explicit different AI
                "id": "sm",
                "user_id": "u1",
                "ai_id": "story_master_v1",
                "user_message": "故事大師記憶",
                "assistant_message": "ok",
                "memory_type": "semantic",
                "importance_score": 0.8,
                "embedding": EMB,
            },
        ]
    )
    eng = RetrievalEngine(ms, graph_manager=None)

    out_default = await eng.retrieve(
        "記憶", conversation_id="c", user_id="u1",
        memory_types=["semantic"], ai_id="xiaochenguang_v1",
        include_v1_conversation=False,
    )
    blob_d = " ".join(i.get("content") or "" for i in out_default["items"])
    assert "沒有ai欄位的舊記憶" in blob_d      # legacy visible to default AI
    assert "故事大師記憶" not in blob_d          # other explicit AI not leaked

    out_other = await eng.retrieve(
        "記憶", conversation_id="c", user_id="u1",
        memory_types=["semantic"], ai_id="story_master_v1",
        include_v1_conversation=False,
    )
    blob_o = " ".join(i.get("content") or "" for i in out_other["items"])
    assert "故事大師記憶" in blob_o              # explicit AI sees its own
    assert "沒有ai欄位的舊記憶" not in blob_o    # legacy NULL not leaked to other AI


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieval_no_starvation_from_other_ai_rows(mem_env):
    """Round 3 P1-A: many other-AI rows must NOT crowd the target-AI row out of the
    DB query limit. Target AI memory must still be recalled; other AI never leaks."""
    from backend.modules.retrieval_engine import RetrievalEngine

    ms, sb, *_ = mem_env
    for i in range(30):
        sb.table("xiaochenguang_memories").rows.append(
            {
                "id": f"o{i}", "user_id": "u1", "ai_id": "other_ai",
                "user_message": f"綠茶其他AI記憶{i}", "assistant_message": "ok",
                "memory_type": "semantic", "importance_score": 0.9, "embedding": EMB,
            }
        )
    sb.table("xiaochenguang_memories").rows.append(
        {
            "id": "target", "user_id": "u1", "ai_id": "story_master_v1",
            "user_message": "綠茶目標AI記憶", "assistant_message": "ok",
            "memory_type": "semantic", "importance_score": 0.5, "embedding": EMB,
        }
    )
    eng = RetrievalEngine(ms, graph_manager=None)
    out = await eng.retrieve(
        "綠茶", conversation_id="c", user_id="u1", memory_types=["semantic"],
        ai_id="story_master_v1", limit=3, include_v1_conversation=False,
    )
    blob = " ".join(i.get("content") or "" for i in out["items"])
    assert "綠茶目標AI記憶" in blob          # target recalled despite 30 other-AI rows
    assert "其他AI記憶" not in blob           # other AI never leaked


@pytest.mark.unit
def test_forward_sql_backfills_legacy_owner_before_not_null():
    """Round 2 migration: forward must backfill NULL owners and only then guard NOT NULL."""
    text = FWD.read_text(encoding="utf-8")
    assert "UPDATE public.xiaochenguang_memories" in text
    assert "ai_id = 'xiaochenguang_v1'" in text
    assert "user_id = 'default_user'" in text
    # NOT NULL must be guarded (only when no NULL remains)
    assert "WHERE ai_id IS NULL" in text
    assert "SET NOT NULL" in text
    rb = RBACK.read_text(encoding="utf-8")
    assert "xiaochenguang_memories" in rb and "DROP NOT NULL" in rb


@pytest.mark.unit
def test_reflections_migration_backfills_user_and_ai_owner():
    """Round 3 P1-B: reflections migration must handle BOTH user_id and ai_id
    (default + backfill + guarded NOT NULL + rollback), not just ai_id."""
    fwd = FWD.read_text(encoding="utf-8")
    rb = RBACK.read_text(encoding="utf-8")

    # SET DEFAULT on both owner columns
    assert re.search(
        r"ALTER TABLE public\.xiaochenguang_reflections ALTER COLUMN user_id\s+SET DEFAULT", fwd
    )
    assert re.search(
        r"ALTER TABLE public\.xiaochenguang_reflections ALTER COLUMN ai_id\s+SET DEFAULT", fwd
    )
    # Backfill NULL/empty for BOTH owner columns
    assert re.search(
        r"UPDATE public\.xiaochenguang_reflections\s+SET user_id = 'default_user'\s+WHERE user_id IS NULL",
        fwd,
    )
    assert re.search(
        r"UPDATE public\.xiaochenguang_reflections\s+SET ai_id = 'xiaochenguang_v1'\s+WHERE ai_id IS NULL",
        fwd,
    )
    # Guarded NOT NULL for BOTH (only after backfill leaves zero NULLs)
    assert "xiaochenguang_reflections WHERE user_id IS NULL" in fwd
    assert "xiaochenguang_reflections WHERE ai_id IS NULL" in fwd
    assert re.search(
        r"ALTER TABLE public\.xiaochenguang_reflections ALTER COLUMN user_id SET NOT NULL", fwd
    )
    assert re.search(
        r"ALTER TABLE public\.xiaochenguang_reflections ALTER COLUMN ai_id SET NOT NULL", fwd
    )
    # Rollback DROP NOT NULL for BOTH reflections owner columns
    assert re.search(
        r"ALTER TABLE public\.xiaochenguang_reflections\s+ALTER COLUMN user_id DROP NOT NULL", rb
    )
    assert re.search(
        r"ALTER TABLE public\.xiaochenguang_reflections\s+ALTER COLUMN ai_id DROP NOT NULL", rb
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_v2_unavailable_degrades_without_cross_owner_leak(mem_env):
    """Gate C: when match_memories_v2 is unavailable (permission denied / missing),
    the app must degrade to the fail-closed traditional path WITHOUT leaking another
    owner's memory."""
    ms, sb, *_ = mem_env
    sb.table("xiaochenguang_memories").rows.extend(
        [
            {"conversation_id": "c", "user_id": "user-a", "ai_id": "xiaochenguang_v1",
             "user_message": "A的秘密綠茶", "assistant_message": "ok", "memory_type": "conversation"},
            {"conversation_id": "c", "user_id": "user-b", "ai_id": "xiaochenguang_v1",
             "user_message": "B的秘密綠茶", "assistant_message": "ok", "memory_type": "conversation"},
        ]
    )

    def _rpc_unavailable(*a, **k):
        raise Exception("permission denied for function match_memories_v2")

    ms.supabase.rpc = _rpc_unavailable  # simulate v2 unavailable

    out = await ms.search_relevant_memories(
        "c", "綠茶", limit=5, user_id="user-a", ai_id="xiaochenguang_v1"
    )
    assert "A的秘密綠茶" in out          # degraded path still recalls the owner's memory
    assert "B的秘密綠茶" not in out       # no cross-owner leak even when v2 is down


@pytest.mark.unit
def test_startup_credentials_return_three_tuple(monkeypatch):
    """Gate C blocker A: _resolve_supabase_credentials() must return (url, key, mode)
    and unpack as three values (guards the former 2-value startup unpack bug)."""
    import backend.supabase_handler as sh

    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    for k in ("SUPABASE_SECRET_KEY", "SUPABASE_ANON_KEY", "SUPABASE_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    t = sh._resolve_supabase_credentials()
    assert len(t) == 3
    url, key, mode = t  # must unpack cleanly as three values
    assert url == "https://x.supabase.co" and mode == "service_role"
    # modern secret key is elevated and ranks just below service_role
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sec")
    assert sh.resolved_key_mode() == "secret"
    assert sh.is_backend_elevated() is True


@pytest.mark.unit
def test_readiness_reports_service_role_only_as_configured(monkeypatch):
    """Gate C blocker B: a backend with ONLY an elevated key must read as
    configured, and readiness must expose a safe key-mode label (no key fragment)."""
    from backend import health

    for k in ("SUPABASE_SECRET_KEY", "SUPABASE_ANON_KEY", "SUPABASE_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-secret-value")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    p = health.readiness_payload(check_dns=False)
    assert p["services"]["supabase_config"] == "configured"
    assert p["services"]["supabase_key_mode"] == "service_role"
    # the raw key value must never appear anywhere in the payload
    import json as _json
    assert "svc-secret-value" not in _json.dumps(p)


@pytest.mark.unit
def test_migration_is_expand_only_leaves_legacy_untouched():
    """Gate C: forward must NOT create/alter/grant legacy match_memories; rollback
    must NOT drop it; smoke must not require a raising legacy stub."""
    fwd = FWD.read_text(encoding="utf-8")
    rb = RBACK.read_text(encoding="utf-8")
    smoke = (ROOT / "supabase" / "migrations" / "task006_pgvector_smoke.sql").read_text(encoding="utf-8")
    # forward: still creates v2, but never a legacy match_memories function/grant
    assert "match_memories_v2" in fwd
    assert not re.search(r"FUNCTION\s+public\.match_memories\s*\(", fwd)
    assert not re.search(r"ON FUNCTION\s+public\.match_memories\s*\(vector", fwd)
    # rollback: drops v2 only, never legacy
    assert "DROP FUNCTION IF EXISTS public.match_memories_v2" in rb
    assert not re.search(r"DROP FUNCTION[^\n]*public\.match_memories\s*\(vector, integer, text\)", rb)
    # smoke: no raising-stub requirement; asserts no public bypass + no legacy created
    assert "should be retired/raise" not in smoke
    assert "has_function_privilege" in smoke


@pytest.mark.unit
def test_supabase_handler_prefers_service_role_key(monkeypatch):
    """P0-3: data-plane key selection prefers service_role; mode is observable."""
    import backend.supabase_handler as sh

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key-value")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-value")
    url, key, mode = sh._resolve_supabase_credentials()
    assert mode == "service_role"
    assert key == "svc-key-value"

    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    url, key, mode = sh._resolve_supabase_credentials()
    assert mode == "anon"
    assert key == "anon-key-value"
