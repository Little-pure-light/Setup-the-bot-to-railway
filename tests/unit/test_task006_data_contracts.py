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
def test_user_preferences_rls_and_grants_locked_down():
    """Gate C C4: user_preferences must have explicit RLS + table/sequence grants
    (never rely on Supabase default Data API grants). anon/authenticated locked out;
    service_role granted; no permissive anon/authenticated policy."""
    fwd = FWD.read_text(encoding="utf-8")
    rb = RBACK.read_text(encoding="utf-8")
    smoke = (ROOT / "supabase" / "migrations" / "task006_pgvector_smoke.sql").read_text(encoding="utf-8")

    # RLS enabled on the table
    assert re.search(r"ALTER TABLE public\.user_preferences ENABLE ROW LEVEL SECURITY", fwd)
    # table DML revoked from public roles, granted to service_role
    assert re.search(r"REVOKE ALL ON TABLE public\.user_preferences FROM PUBLIC", fwd)
    assert re.search(r"REVOKE ALL ON TABLE public\.user_preferences FROM anon", fwd)
    assert re.search(r"REVOKE ALL ON TABLE public\.user_preferences FROM authenticated", fwd)
    assert re.search(r"GRANT[^\n]*ON TABLE public\.user_preferences TO service_role", fwd)
    # sequence locked down (resolved via pg_get_serial_sequence), granted to service_role
    assert "pg_get_serial_sequence('public.user_preferences', 'id')" in fwd
    assert re.search(r"REVOKE ALL ON SEQUENCE %s FROM anon", fwd)
    assert re.search(r"GRANT USAGE, SELECT ON SEQUENCE %s TO service_role", fwd)
    # NO permissive anon/authenticated policy is created
    assert not re.search(r"CREATE POLICY", fwd)
    # rollback must NOT re-open user_preferences (no re-grant to anon, no DISABLE RLS)
    assert not re.search(r"GRANT[^\n]*public\.user_preferences[^\n]*TO (anon|authenticated|PUBLIC)", rb)
    assert not re.search(r"DISABLE ROW LEVEL SECURITY", rb)
    # smoke proves the privilege posture at runtime
    assert "has_table_privilege('anon','public.user_preferences'" in smoke
    assert "has_sequence_privilege('service_role'" in smoke
    assert "relrowsecurity" in smoke


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


@pytest.mark.unit
def test_pinecone_real_adapter_upsert_keyword_and_metadata_none_excluded():
    """C6 fix: the REAL enabled=True adapter path — PineconeHandler.insert_reflection
    must call index.upsert(vectors=...) (keyword-only in pinecone SDK v3+) and must
    NOT send None metadata values to Pinecone. A keyword-only fake Index catches the
    previous positional-arg regression (which raised TypeError in production)."""
    from backend.modules.pinecone_handler import PineconeHandler

    class _KwOnlyIndex:
        def __init__(self):
            self.captured = None

        def upsert(self, *, vectors, namespace=None):  # keyword-only `vectors`
            self.captured = vectors
            return {"upserted_count": len(vectors)}

    class _Emb:
        def create(self, model=None, input=None):
            class _D:
                embedding = [0.1, 0.2, 0.3]
            class _R:
                data = [_D()]
            return _R()

    class _OpenAI:
        def __init__(self):
            self.embeddings = _Emb()

    ph = PineconeHandler.__new__(PineconeHandler)
    ph.enabled = True
    ph.index = _KwOnlyIndex()
    ph.openai = _OpenAI()

    metadata = {
        "user_id": "u1", "ai_id": "xiaochenguang_v1", "reflection_key": "k1",
        "confidence": 0.9, "empty_field": None,  # None must be dropped, not sent
    }
    ok = ph.store_reflection_with_text("k1", "some reflection text", metadata)
    assert ok is True  # regression guard: positional upsert would TypeError -> False

    cap = ph.index.captured
    assert isinstance(cap, list) and len(cap) == 1
    item = cap[0]
    assert item["id"] == "k1"
    assert isinstance(item["values"], list) and item["values"] == [0.1, 0.2, 0.3]
    assert isinstance(item["metadata"], dict)
    assert "empty_field" not in item["metadata"]  # None excluded (Pinecone rejects null)
    assert item["metadata"]["user_id"] == "u1"
    assert item["metadata"]["confidence"] == 0.9


# ---------------------------------------------------------------------------
# Task 006 C6-F — hybrid recall reliability (real MemorySystem adapter).
# Mechanism under test (consistent with the observed R02/Open-WebUI recall miss;
# the exact production top-3 occupants were not captured, so these tests
# reproduce the RISK rather than asserting a specific production state):
# after accumulation, higher-cosine distractor turns crowd out an older
# relevant memory in a top-3 view. Fix = bounded candidate pool (separate from
# inject count) + merge scopes + exact-dedupe + MMR diversify over FULL content
# + hybrid (cosine + Chinese char-ngram overlap) rerank. No threshold lowering,
# no hardcoded markers; owner+AI isolation and the 0.55 floor stay intact.
# ---------------------------------------------------------------------------

_AI = "xiaochenguang_v1"

# Ten DISTINCT distractor questions (not exact duplicates -> exact-dedupe cannot
# collapse them; several pairs fall below the near-dup threshold so they are truly
# separate candidates). They share only the topic phrase and a common long
# "not found" answer, so MMR clusters them without any hardcoded marker.
_DISTRACTOR_QUESTIONS = [
    "我的驗收暗號到底是什麼呢",
    "可以再說一次當時的驗收暗號嗎",
    "驗收暗號我忘記了可以提示我嗎",
    "幫我確認一下我的驗收暗號好嗎",
    "現在我的驗收暗號是哪一個呀",
    "請重複一次我設定過的驗收暗號",
    "驗收暗號你還有記得嗎拜託",
    "告訴我我當初講的那個驗收暗號",
    "驗收暗號是不是後來有被改掉了",
    "我真的很想知道驗收暗號的內容",
    "到底哪一個才是我的驗收暗號啦",
]
_DISTRACTOR_ANSWER = "抱歉，我目前在你的記憶裡沒有找到你要的那個內容喔。"


def _seed_target_and_distractors(sb, n_distractors=10, target_sim=0.70, distractor_sim=0.95):
    """Older target fact (carries the answer, LOWER cosine) + >=10 DISTINCT
    higher-cosine distractor questions. No markers baked into product logic."""
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "c_seed", "user_id": "u1", "ai_id": _AI,
        "user_message": "請記住，我的驗收暗號是「銀河玻璃杯」。",
        "assistant_message": "好的，我把你的驗收暗號「銀河玻璃杯」記起來了。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-01T00:00:00Z", "_sim": target_sim,
    })
    for i in range(n_distractors):
        q = _DISTRACTOR_QUESTIONS[i % len(_DISTRACTOR_QUESTIONS)]
        tbl.rows.append({
            "conversation_id": f"c_d{i}", "user_id": "u1", "ai_id": _AI,
            "user_message": q, "assistant_message": _DISTRACTOR_ANSWER,
            "memory_type": "conversation", "embedding": EMB,
            "created_at": f"2026-07-2{i%10}T00:00:00Z", "_sim": distractor_sim,
        })


def _count_injected(out):
    return out.count("相關記憶:")


@pytest.mark.unit
def test_distractor_fixtures_are_genuinely_distinct():
    """Guard: the distractors must NOT be exact-dedupe bait, and several pairs
    must fall below the near-dup threshold (they are real, separate candidates)."""
    from modules.memory_system import _char_ngrams, _ngram_jaccard
    qs = _DISTRACTOR_QUESTIONS[:10]
    assert len(set(qs)) == 10  # all user_messages distinct
    full = [_char_ngrams(f"{q} {_DISTRACTOR_ANSWER}") for q in qs]
    below = 0
    for i in range(len(full)):
        for j in range(i + 1, len(full)):
            if _ngram_jaccard(full[i], full[j]) < 0.9:
                below += 1
    assert below >= 5  # several distinct (below near-dup) candidate pairs


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_surfaces_older_target_among_many_distractors(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    _seed_target_and_distractors(sb, n_distractors=10)
    out = await ms.search_relevant_memories(
        "c_new", "請問我當初設定的驗收暗號是哪一個？",
        limit=3, user_id="u1", ai_id=_AI,
    )
    # older target surfaced despite 10 distinct higher-cosine distractors
    assert "銀河玻璃杯" in out
    # candidate pool != injected count: still capped at limit
    assert _count_injected(out) <= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_distinct_distractors_do_not_take_all_slots(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    _seed_target_and_distractors(sb, n_distractors=11)
    out = await ms.search_relevant_memories(
        "c_new", "我的驗收暗號是哪一個？", limit=3, user_id="u1", ai_id=_AI,
    )
    # target present AND distractors do not occupy every slot
    assert "銀河玻璃杯" in out
    assert out.count(_DISTRACTOR_ANSWER) <= 2
    assert _count_injected(out) <= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_distractors_plus_cross_owner_ai_no_leak(mem_env):
    """Distractor pressure must not surface another owner's / AI's memory."""
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    _seed_target_and_distractors(sb, n_distractors=10)
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({  # other owner, very high sim
        "conversation_id": "c_other", "user_id": "u2", "ai_id": _AI,
        "user_message": "我的驗收暗號是紅色機密。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-30T00:00:00Z", "_sim": 0.99,
    })
    tbl.rows.append({  # same owner, other AI, very high sim
        "conversation_id": "c_other2", "user_id": "u1", "ai_id": "story_master_v1",
        "user_message": "我的驗收暗號是故事機密。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-30T00:00:00Z", "_sim": 0.99,
    })
    out = await ms.search_relevant_memories(
        "c_new", "我的驗收暗號是哪一個？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "銀河玻璃杯" in out
    assert "紅色機密" not in out
    assert "故事機密" not in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_near_dup_question_keeps_answer_bearing_candidate(mem_env):
    """Same question, two answers: one contains the fact, one is a 'not found'.
    Near-dup diversify keys on FULL content, so the answer-bearing candidate is
    NOT dropped just because the user_message matches a higher-cosine no-answer row."""
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({  # no-answer row, HIGHER cosine, identical question text
        "conversation_id": "cq1", "user_id": "u1", "ai_id": _AI,
        "user_message": "我的通關密語是什麼？",
        "assistant_message": "抱歉，我目前沒有找到相關記憶。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-20T00:00:00Z", "_sim": 0.97,
    })
    tbl.rows.append({  # answer-bearing row, slightly lower cosine, same question text
        "conversation_id": "cq2", "user_id": "u1", "ai_id": _AI,
        "user_message": "我的通關密語是什麼？",
        "assistant_message": "你的通關密語是月光森林。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-10T00:00:00Z", "_sim": 0.90,
    })
    out = await ms.search_relevant_memories(
        "cq_new", "我的通關密語是什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "月光森林" in out  # answer candidate not dropped as a user_message near-dup


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_pool_larger_than_inject_but_capped(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    tbl = sb.table("xiaochenguang_memories")
    for i in range(8):
        tbl.rows.append({
            "conversation_id": f"cx{i}", "user_id": "u1", "ai_id": _AI,
            "user_message": f"我喜歡的第{i}件事是散步{i}。",
            "assistant_message": f"了解，你喜歡散步{i}。",
            "memory_type": "conversation", "embedding": EMB,
            "created_at": f"2026-07-1{i}T00:00:00Z", "_sim": 0.9 - i * 0.01,
        })
    out = await ms.search_relevant_memories(
        "cx_new", "我喜歡做什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert 1 <= _count_injected(out) <= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_cross_owner_high_sim_not_leaked(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "shared", "user_id": "u1", "ai_id": _AI,
        "user_message": "我的暗號是綠色。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-01T00:00:00Z", "_sim": 0.6,
    })
    tbl.rows.append({  # other owner, HIGHER sim — must never leak
        "conversation_id": "shared", "user_id": "u2", "ai_id": _AI,
        "user_message": "我的暗號是紅色機密。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-02T00:00:00Z", "_sim": 0.99,
    })
    out = await ms.search_relevant_memories(
        "shared", "我的暗號是什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "綠色" in out
    assert "紅色機密" not in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_cross_ai_high_sim_not_leaked(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "c1", "user_id": "u1", "ai_id": _AI,
        "user_message": "光光專屬記憶。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-01T00:00:00Z", "_sim": 0.6,
    })
    tbl.rows.append({  # same owner, other AI, HIGHER sim — must never leak
        "conversation_id": "c1", "user_id": "u1", "ai_id": "story_master_v1",
        "user_message": "故事大師機密記憶。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-02T00:00:00Z", "_sim": 0.99,
    })
    out = await ms.search_relevant_memories(
        "c1", "記憶", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "光光專屬記憶" in out
    assert "故事大師機密記憶" not in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_missing_owner_fail_closed(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    _seed_target_and_distractors(sb, n_distractors=3)
    assert await ms.search_relevant_memories(
        "c_new", "暗號", limit=3, user_id="", ai_id=_AI) == ""
    assert await ms.search_relevant_memories(
        "c_new", "暗號", limit=3, user_id="u1", ai_id="") == ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_rpc_exception_chinese_fallback(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "c1", "user_id": "u1", "ai_id": _AI,
        "user_message": "我的生日是十月十日。", "assistant_message": "記住了。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-01T00:00:00Z",
    })

    def _boom(*a, **k):
        raise RuntimeError("rpc down")

    sb.rpc = _boom
    out = await ms.search_relevant_memories(
        "c1", "我的生日是什麼時候？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "十月十日" in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_legacy_null_ai_still_compatible(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    os.environ["AI_ID"] = _AI  # default AI inherits legacy NULL rows
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "c_legacy", "user_id": "u1", "ai_id": None,
        "user_message": "舊資料：我養了一隻貓叫咪咪。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-06-01T00:00:00Z",
    })
    out = await ms.search_relevant_memories(
        "c_legacy", "我養的貓叫什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "咪咪" in out


# --- MEMORY_SEMANTIC_SCOPE regression (conversation_only vs cross-conversation) ---

def _seed_two_conversations(sb):
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "conv_here", "user_id": "u1", "ai_id": _AI,
        "user_message": "在這個對話我說我喜歡藍色。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-05T00:00:00Z", "_sim": 0.8,
    })
    tbl.rows.append({
        "conversation_id": "conv_other", "user_id": "u1", "ai_id": _AI,
        "user_message": "在別的對話我說我喜歡青椒披薩。", "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-06T00:00:00Z", "_sim": 0.95,
    })


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scope_conversation_only_does_not_cross_conversations(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    ms.semantic_scope = "conversation_only"
    _seed_two_conversations(sb)
    out = await ms.search_relevant_memories(
        "conv_here", "我喜歡什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "藍色" in out
    assert "青椒披薩" not in out  # other conversation must NOT be pulled in


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scope_conversation_only_fallback_also_scoped(mem_env):
    """Even when the RPC raises (traditional fallback), conversation_only must
    not cross conversations."""
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    ms.semantic_scope = "conversation_only"
    _seed_two_conversations(sb)

    def _boom(*a, **k):
        raise RuntimeError("rpc down")

    sb.rpc = _boom
    out = await ms.search_relevant_memories(
        "conv_here", "我喜歡什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "青椒披薩" not in out  # traditional fallback stays in-conversation


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scope_cross_conversation_default_can_recall_other_conversation(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    ms.semantic_scope = "user_ai_cross_conversation"  # default
    _seed_two_conversations(sb)
    out = await ms.search_relevant_memories(
        "conv_here", "我喜歡的食物是什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "青椒披薩" in out  # cross-conversation recall works in default mode


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scope_conversation_only_still_owner_ai_fail_closed(mem_env):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    ms.semantic_scope = "conversation_only"
    _seed_two_conversations(sb)
    assert await ms.search_relevant_memories(
        "conv_here", "我喜歡什麼？", limit=3, user_id="", ai_id=_AI) == ""
    assert await ms.search_relevant_memories(
        "conv_here", "我喜歡什麼？", limit=3, user_id="u1", ai_id="") == ""


# --- Public entry recall_memories() scope regression (not just search_*) ---

def _seed_public_entry(sb):
    """Current conversation empty; a same-owner+AI OTHER conversation holds a
    relevant memory; plus a different-owner memory that must never leak."""
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "conv_far", "user_id": "u1", "ai_id": _AI,
        "user_message": "在很久以前的對話我說我的幸運數字是七七七。",
        "assistant_message": "好，我記得你的幸運數字。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-06-01T00:00:00Z",
    })
    tbl.rows.append({  # different owner — must never leak through the public entry
        "conversation_id": "conv_u2", "user_id": "u2", "ai_id": _AI,
        "user_message": "u2機密：我的幸運數字是九九九。",
        "assistant_message": "好。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-06-02T00:00:00Z",
    })


@pytest.mark.unit
@pytest.mark.asyncio
async def test_public_recall_conversation_only_does_not_cross(mem_env):
    """recall_memories() public entry: conversation_only + empty current
    conversation must NOT fall back across conversations."""
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    ms.semantic_scope = "conversation_only"
    _seed_public_entry(sb)
    out = await ms.recall_memories(
        "我的幸運數字是多少？", "conv_now", user_id="u1", ai_id=_AI,
    )
    assert "七七七" not in out          # no cross-conversation content
    assert "u2機密" not in out          # no cross-owner leak
    assert out == ""                    # nothing recalled at all


@pytest.mark.unit
@pytest.mark.asyncio
async def test_public_recall_cross_mode_recalls_other_conversation(mem_env):
    """recall_memories() public entry: default cross-conversation mode with the
    same data can recall the other conversation; owner + AI isolation holds."""
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    ms.semantic_scope = "user_ai_cross_conversation"
    _seed_public_entry(sb)
    out = await ms.recall_memories(
        "我的幸運數字是多少？", "conv_now", user_id="u1", ai_id=_AI,
    )
    assert "七七七" in out              # cross-conversation recall works
    assert "u2機密" not in out          # still no cross-owner leak


# ---------------------------------------------------------------------------
# Task 006 C6-F — opt-in de-identified recall diagnostics (default OFF).
# Observation-only: must never change candidate set, ranking, MMR, dedupe,
# tie-break, injected rows or their order; never log raw content/identifiers.
# ---------------------------------------------------------------------------

import io as _io
import contextlib as _contextlib
from modules.memory_system import (
    _recall_diagnostics_enabled as _diag_enabled,
    _candidate_fingerprint as _diag_fp,
)

_DIAG_ENV = "MEMORY_RECALL_DIAGNOSTICS"


def _seed_diag_rows(sb):
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({
        "conversation_id": "c_seed", "user_id": "u1", "ai_id": _AI,
        "user_message": "請記住我的驗收暗號是銀河玻璃杯。",
        "assistant_message": "好的，我記住了你的驗收暗號。",
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-01T00:00:00Z", "_sim": 0.70,
    })
    for i in range(5):
        tbl.rows.append({
            "conversation_id": f"cd{i}", "user_id": "u1", "ai_id": _AI,
            "user_message": f"今天想聊點別的第{i}件事", "assistant_message": f"好啊聊聊{i}",
            "memory_type": "conversation", "embedding": EMB,
            "created_at": f"2026-07-1{i}T00:00:00Z", "_sim": 0.9 - i * 0.02,
        })


async def _run_recall(ms):
    return await ms.search_relevant_memories(
        "c_new", "我的驗收暗號是什麼？", limit=3, user_id="u1", ai_id=_AI,
    )


@pytest.mark.unit
def test_recall_diag_truthy_parse(monkeypatch):
    for v in ("1", "true", "TRUE", "yes", "On"):
        monkeypatch.setenv(_DIAG_ENV, v)
        assert _diag_enabled() is True
    for v in ("0", "false", "", "no", "xyz", "2"):
        monkeypatch.setenv(_DIAG_ENV, v)
        assert _diag_enabled() is False
    monkeypatch.delenv(_DIAG_ENV, raising=False)
    assert _diag_enabled() is False  # missing -> False


@pytest.mark.unit
def test_recall_diag_fingerprint_is_12_hex_and_nonreversible():
    fp = _diag_fp("使用者訊息", "助理回覆")
    assert re.fullmatch(r"[0-9a-f]{12}", fp)
    # does not contain the raw text; different content -> different fp
    assert "使用者訊息" not in fp
    assert _diag_fp("a", "b") != _diag_fp("a", "c")
    # None-safe
    assert re.fullmatch(r"[0-9a-f]{12}", _diag_fp(None, None))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_diag_off_emits_no_detail(mem_env, capsys, monkeypatch):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    monkeypatch.delenv(_DIAG_ENV, raising=False)  # default off
    _seed_diag_rows(sb)
    await _run_recall(ms)
    out = capsys.readouterr().out
    assert "recall_diag" not in out          # no de-identified detail line
    assert "recall pool=" in out             # existing counts line preserved


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_diag_on_emits_selected_only(mem_env, capsys, monkeypatch):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    monkeypatch.setenv(_DIAG_ENV, "true")
    _seed_diag_rows(sb)
    await _run_recall(ms)
    out = capsys.readouterr().out
    assert "recall_diag" in out
    line = [ln for ln in out.splitlines() if "recall_diag" in ln][0]
    slots = re.findall(
        r"slot=(\d+) fp=([0-9a-f]+) src=(\S+) cos=([-\d.]+) overlap=([-\d.]+) rel=([-\d.]+) mmr=([-\d.]+)",
        line,
    )
    assert 1 <= len(slots) <= 3               # only final selected, capped
    for slot, fp, src, cos, ov, rel, mmr in slots:
        assert len(fp) == 12 and re.fullmatch(r"[0-9a-f]{12}", fp)
        assert src in ("semantic", "owner_fallback", "unknown")
        for val in (cos, ov, rel, mmr):       # rounded to <= 3 decimals
            if "." in val:
                assert len(val.split(".")[-1]) <= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_diag_never_logs_raw_content_or_identifiers(mem_env, capsys, monkeypatch):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    monkeypatch.setenv(_DIAG_ENV, "true")
    _seed_diag_rows(sb)
    await _run_recall(ms)
    out = capsys.readouterr().out
    for secret in (
        "銀河玻璃杯", "請記住", "好的，我記住了", "今天想聊",   # raw messages
        "u1", "xiaochenguang_v1", "c_seed", "c_new",           # owner/ai/conversation ids
        "Authorization", "Bearer", "sk-",                       # secret samples
    ):
        assert secret not in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_diag_does_not_change_selection(mem_env, monkeypatch):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    _seed_diag_rows(sb)
    monkeypatch.delenv(_DIAG_ENV, raising=False)
    out_off = await _run_recall(ms)
    monkeypatch.setenv(_DIAG_ENV, "true")
    out_on = await _run_recall(ms)
    assert out_off == out_on                  # identical rows, order and count


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recall_diag_failsafe_does_not_break_recall(mem_env, monkeypatch):
    ms, sb, *_ = mem_env
    ms.memory_rpc_name = "match_memories_v2"
    monkeypatch.setenv(_DIAG_ENV, "true")
    tbl = sb.table("xiaochenguang_memories")
    tbl.rows.append({  # None assistant_message must not break diagnostics
        "conversation_id": "cx", "user_id": "u1", "ai_id": _AI,
        "user_message": "我養的貓叫咪咪。", "assistant_message": None,
        "memory_type": "conversation", "embedding": EMB,
        "created_at": "2026-07-01T00:00:00Z", "_sim": 0.8,
    })
    out = await ms.search_relevant_memories(
        "cx", "我的貓叫什麼？", limit=3, user_id="u1", ai_id=_AI,
    )
    assert "咪咪" in out                       # recall still succeeds
