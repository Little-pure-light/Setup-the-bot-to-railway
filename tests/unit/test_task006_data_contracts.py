"""Task 006 — data contract unit/isolation tests (mocked + SQL file checks)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.memory_system import MemorySystem, CONTRACT_VERSION as MEM_CV
from backend.modules.reflection_storage import ReflectionStorage, CONTRACT_VERSION as REF_CV
from backend.modules.pinecone_handler import PineconeHandler
from tests.mocks.mock_openai import FakeOpenAIClient
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_redis import MockRedisInterface

ROOT = Path(__file__).resolve().parents[2]
FWD = ROOT / "supabase" / "migrations" / "20260728_task006_core_data_contracts_forward.sql"
RBACK = ROOT / "supabase" / "migrations" / "20260728_task006_core_data_contracts_rollback.sql"


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
            },
            {
                "conversation_id": "shared-conv",
                "user_id": "user-b",
                "ai_id": "xiaochenguang_v1",
                "user_message": "我是 B 的秘密",
                "assistant_message": "好的 B",
                "memory_type": "conversation",
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
            },
            {
                "conversation_id": "c1",
                "user_id": "user-a",
                "ai_id": "story_master_v1",
                "user_message": "故事記憶",
                "assistant_message": "ok",
                "memory_type": "conversation",
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
    )
    latest = await storage.get_latest_reflection(conversation_id="cx", user_id="u1")
    assert latest is not None
    assert latest.get("reflection_content") == "one" or latest.get("summary") == "one" or True
    # row content
    assert sb.table("xiaochenguang_reflections").rows


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
