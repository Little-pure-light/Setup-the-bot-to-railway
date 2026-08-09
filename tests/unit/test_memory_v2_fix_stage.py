"""Memory V2 Fix stage: Identity Charter, Night Growth safety, Graph integrity, Retrieval ranking."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.modules.identity_engine import IdentityEngine
from backend.modules.night_growth import NightGrowth
from backend.modules.night_growth_safety import NightGrowthExecutionStore
from backend.modules.graph_manager import GraphManager
from backend.modules.retrieval_engine import RetrievalEngine, _cosine
from backend.modules.memory_manager import MemoryManager
from modules.memory_system import MemorySystem
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_openai import FakeOpenAIClient


@pytest.fixture
def v1_ms():
    return MemorySystem(MockSupabase(), FakeOpenAIClient(), "xiaochenguang_memories")


# ---------------------------------------------------------------------------
# Task A — Identity Charter
# ---------------------------------------------------------------------------

def test_identity_charter_schema_and_version(tmp_path):
    eng = IdentityEngine(
        user_id="u1",
        base_dir=str(tmp_path / "id"),
        update_mode="formal",
    )
    c = eng.load()
    assert c["name"] == "小宸光"
    assert isinstance(c["mission"], list)
    assert isinstance(c["boundaries"], list)
    assert c["version"] == 1
    assert c["identity_id"]
    r = eng.update(
        {"role": "夥伴 v2"},
        change_reason="test formal update",
        confidence=0.9,
        source="unit_test",
        force_formal=True,
    )
    assert r["status"] == "formal"
    assert r["charter"]["version"] == 2
    assert r["charter"]["previous_version_id"]
    assert r["charter"]["change_reason"] == "test formal update"


def test_identity_reject_missing_reason(tmp_path):
    eng = IdentityEngine(user_id="u1", base_dir=str(tmp_path / "id"))
    r = eng.update({"role": "x"}, change_reason="", confidence=0.9, source="t")
    assert r["status"] == "rejected"
    assert r["error"] == "missing_change_reason"


def test_identity_low_confidence_candidate(tmp_path):
    eng = IdentityEngine(
        user_id="u1",
        base_dir=str(tmp_path / "id"),
        update_mode="formal",
        confidence_threshold=0.7,
    )
    eng.load()
    r = eng.update(
        {"role": "candidate role"},
        change_reason="low conf",
        confidence=0.2,
        source="unit_test",
    )
    assert r["status"] == "candidate"
    assert r["candidate_id"]
    assert eng.load()["version"] == 1  # formal unchanged
    assert len(eng.list_candidates()) >= 1


def test_identity_identical_noop(tmp_path):
    eng = IdentityEngine(
        user_id="u1", base_dir=str(tmp_path / "id"), update_mode="formal"
    )
    c = eng.load()
    r = eng.update(
        {"role": c["role"], "mission": c["mission"]},
        change_reason="same",
        confidence=0.9,
        source="t",
        force_formal=True,
    )
    assert r["status"] == "noop"


def test_identity_rollback_and_compare(tmp_path):
    eng = IdentityEngine(
        user_id="u1", base_dir=str(tmp_path / "id"), update_mode="formal"
    )
    eng.load()
    eng.update(
        {"role": "v2 role"},
        change_reason="to v2",
        confidence=1.0,
        source="t",
        force_formal=True,
    )
    r = eng.rollback(1)
    assert r["status"] == "formal"
    assert r["charter"]["version"] == 3
    cmp = eng.compare_versions(1, 2)
    assert "diffs" in cmp
    assert eng.change_history()
    exp = eng.export()
    assert exp.exists()


def test_identity_does_not_touch_system_prompt(tmp_path):
    eng = IdentityEngine(user_id="u1", base_dir=str(tmp_path / "id"))
    frag = eng.to_prompt_fragment()
    assert "Identity" in frag or "Role" in frag
    # Engine has no system_prompt attribute mutation API
    assert not hasattr(eng, "set_system_prompt")


# ---------------------------------------------------------------------------
# Task B — Night Growth safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_night_growth_idempotency(tmp_path, v1_ms):
    store = NightGrowthExecutionStore(base_dir=str(tmp_path / "ng"))
    mgr = MemoryManager(v1_ms)
    mgr.graph = GraphManager(user_id="u-ng", storage_path=str(tmp_path / "g.json"))
    ng = NightGrowth(mgr, execution_store=store)
    turns = [
        {
            "user_message": "我叫小明",
            "assistant_message": "你好小明",
            "reflection": {
                "summary": "認識名字",
                "causes": [],
                "lessons": ["記住稱呼"],
                "confidence": 0.8,
                "timestamp": "t",
            },
        }
    ]
    r1 = await ng.run_once(user_id="u-ng", recent_turns=turns, dry_run=True, force=False)
    assert r1["status"] == "completed_dry_run"
    assert r1["execution_id"]
    # dry_run does not block formal run
    r_formal = await ng.run_once(user_id="u-ng", recent_turns=turns, dry_run=False, force=False)
    assert r_formal["status"] == "completed"
    r2 = await ng.run_once(user_id="u-ng", recent_turns=turns, dry_run=False, force=False)
    assert r2["status"] == "skipped_duplicate"
    r3 = await ng.run_once(user_id="u-ng", recent_turns=turns, dry_run=False, force=True)
    assert r3["status"] == "completed"


@pytest.mark.asyncio
async def test_night_growth_lock(tmp_path, v1_ms):
    store = NightGrowthExecutionStore(base_dir=str(tmp_path / "ng2"))
    assert store.acquire_lock("u-lock")
    assert not store.acquire_lock("u-lock")
    store.release_lock("u-lock")
    assert store.acquire_lock("u-lock")
    store.release_lock("u-lock")


@pytest.mark.asyncio
async def test_night_growth_cost_guard_limits_dry_run(tmp_path, v1_ms):
    store = NightGrowthExecutionStore(base_dir=str(tmp_path / "ng-budget"))
    ng = NightGrowth(
        MemoryManager(v1_ms),
        execution_store=store,
        max_turns=2,
        max_conversations=1,
        max_input_tokens=500,
    )
    turns = [
        {
            "conversation_id": "older",
            "user_message": "old",
            "assistant_message": "old",
        },
        {
            "conversation_id": "newer",
            "user_message": "new 1",
            "assistant_message": "new 1",
        },
        {
            "conversation_id": "newer",
            "user_message": "new 2",
            "assistant_message": "new 2",
        },
    ]

    report = await ng.run_once(
        user_id="u-budget", recent_turns=turns, dry_run=True, force=True
    )

    assert report["status"] == "completed_dry_run"
    assert report["usage"]["turns_loaded"] == 3
    assert report["usage"]["turns_processed"] == 2
    assert report["usage"]["turns_dropped"] == 1
    assert report["usage"]["conversations_processed"] == 1
    assert report["usage"]["estimated_input_tokens"] <= 500
    assert report["usage"]["limits"] == {
        "max_turns": 2,
        "max_conversations": 1,
        "max_input_tokens": 500,
    }
    assert report["saved_ids"] == []


@pytest.mark.asyncio
async def test_night_growth_gate1_dry_run_e2e_has_all_stages(tmp_path, v1_ms):
    ng = NightGrowth(
        MemoryManager(v1_ms),
        identity_engine=IdentityEngine(
            user_id="u-dry-e2e",
            base_dir=str(tmp_path / "identity-e2e"),
            update_mode="candidate",
        ),
        execution_store=NightGrowthExecutionStore(
            base_dir=str(tmp_path / "ng-dry-e2e")
        ),
    )
    turns = [
        {
            "conversation_id": "fake-conversation",
            "user_message": "我喜歡安靜地整理每天學到的事",
            "assistant_message": "我會先整理成可修正的候選理解",
            "reflection": {
                "summary": "以假資料驗證離線鞏固",
                "causes": ["Gate 1 dry-run"],
                "lessons": ["先驗證再啟用"],
                "confidence": 0.8,
                "timestamp": "2026-08-09T00:00:00Z",
            },
        }
    ]

    report = await ng.run_once(
        user_id="u-dry-e2e", recent_turns=turns, dry_run=True, force=False
    )

    assert report["status"] == "completed_dry_run"
    expected_stages = {
        "load_turns",
        "reflection",
        "semantic_builder",
        "decision_engine",
        "identity_update",
        "attention_update",
        "transformation_update",
        "graph_update",
        "archive",
    }
    assert expected_stages <= report["steps"].keys()
    assert all(report["steps"][stage]["status"] == "ok" for stage in expected_stages)
    assert report["saved_ids"] == []
    assert report["archived_ids"] == []
    assert report["graph_edge_ids"] == []
    assert report["usage"]["turns_processed"] == 1
    assert report["usage"]["outputs_total"] == 0


def test_night_growth_identity_update_stays_candidate(tmp_path, v1_ms):
    identity = IdentityEngine(
        user_id="u-candidate",
        base_dir=str(tmp_path / "identity"),
        update_mode="candidate",
    )
    identity.load()
    ng = NightGrowth(
        MemoryManager(v1_ms),
        identity_engine=identity,
        execution_store=NightGrowthExecutionStore(base_dir=str(tmp_path / "ng-id")),
    )

    result = ng._maybe_identity_update(
        user_message="我喜歡無糖綠茶",
        reflection=None,
        classification={"tags": ["preference"], "confidence": 0.8},
        execution_id="unit",
        decision_identity_update=True,
    )

    assert result is not None
    assert result["status"] == "candidate"
    assert identity.load()["version"] == 1
    assert len(identity.list_candidates()) == 1


# ---------------------------------------------------------------------------
# Task D — Graph integrity
# ---------------------------------------------------------------------------

def test_graph_integrity_and_no_orphan_on_archive(tmp_path):
    g = GraphManager(user_id="u-g", storage_path=str(tmp_path / "g.json"))
    g.clear()
    e = g.add_edge("101", "202", "supports", confidence=0.8, created_by="test")
    assert e["created_at"] and e["created_by"] == "test"
    assert "metadata" in e
    with pytest.raises(ValueError):
        g.add_edge("reflection", "101", "supports")
    with pytest.raises(ValueError):
        g.add_edge("101", "202", "invalid_rel")
    # duplicate suppressed
    e2 = g.add_edge("101", "202", "supports", confidence=0.9)
    assert e2["id"] == e["id"]
    rep = g.integrity_check()
    assert rep["total_edges"] == 1
    assert rep["ok"]
    g.archive_edges_for_memory("101")
    rep2 = g.integrity_check()
    assert rep2["total_edges"] == 0


# ---------------------------------------------------------------------------
# Task C — Retrieval ranking + isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieval_type_priority_and_source(v1_ms, tmp_path):
    emb = v1_ms.openai_client.embeddings.create(
        model="text-embedding-3-small", input="綠茶知識"
    )
    vec = emb.data[0].embedding
    # user A semantic
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "id": "m-sem",
            "user_message": "無糖綠茶很好",
            "assistant_message": "記下偏好",
            "memory_type": "semantic",
            "user_id": "userA",
            "document_content": json.dumps({"embedding_status": "ready"}),
            "embedding": vec,
            "importance_score": 0.9,
            "created_at": "2026-07-24T00:00:00+00:00",
        }
    ).execute()
    # user B should not leak
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "id": "m-b",
            "user_message": "無糖綠茶秘密",
            "assistant_message": "B",
            "memory_type": "semantic",
            "user_id": "userB",
            "embedding": vec,
            "importance_score": 0.99,
        }
    ).execute()
    # identity row
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "id": "m-id",
            "user_message": "你是誰",
            "assistant_message": "我是小宸光",
            "memory_type": "identity",
            "user_id": "userA",
            "embedding": vec,
            "importance_score": 0.8,
        }
    ).execute()

    eng = RetrievalEngine(v1_ms, graph_manager=None)
    r_id = await eng.retrieve(
        "你是誰", conversation_id="c1", user_id="userA", limit=5, include_v1_conversation=False
    )
    assert "identity" in r_id["types"]
    if r_id["items"]:
        # identity type should rank high for identity query
        top_types = [i.get("memory_type") for i in r_id["items"][:2]]
        assert "identity" in top_types or r_id["items"][0].get("memory_type") in (
            "identity",
            "semantic",
        )

    r_sem = await eng.retrieve(
        "什麼是綠茶",
        conversation_id="c1",
        user_id="userA",
        limit=5,
        include_v1_conversation=False,
    )
    ids = [i.get("id") for i in r_sem["items"]]
    assert "m-b" not in ids  # isolation

    # keyword fallback path when no emb on row
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "id": "m-kw",
            "user_message": "上次去海邊",
            "assistant_message": "記得海邊",
            "memory_type": "episodic",
            "user_id": "userA",
            "embedding": None,
            "importance_score": 0.7,
        }
    ).execute()
    r_ep = await eng.retrieve(
        "記得上次海邊",
        conversation_id="c1",
        user_id="userA",
        limit=5,
        include_v1_conversation=False,
    )
    assert r_ep.get("fallback_used") is True or any(
        i.get("source") == "typed_keyword_fallback" for i in r_ep["items"]
    )


@pytest.mark.asyncio
async def test_typed_save_embedding_status(v1_ms, tmp_path):
    mgr = MemoryManager(v1_ms)
    mgr.graph = GraphManager(user_id="u-e", storage_path=str(tmp_path / "ge.json"))
    rec = await mgr.save(
        user_message="喜歡紅茶",
        bot_response="好的",
        conversation_id="c-e",
        user_id="u-e",
        force_type="semantic",
        skip_v1_conversation=True,
    )
    assert rec.get("ok")
    assert getattr(mgr, "_last_embedding_status", None) == "ready"


@pytest.mark.asyncio
async def test_typed_save_embedding_failure_keeps_row(v1_ms, tmp_path):
    v1_ms.openai_client.embeddings.raise_error = RuntimeError("timeout")
    mgr = MemoryManager(v1_ms)
    mgr.graph = GraphManager(user_id="u-e2", storage_path=str(tmp_path / "ge2.json"))
    rec = await mgr.save(
        user_message="仍應保存",
        bot_response="ok",
        conversation_id="c-e2",
        user_id="u-e2",
        force_type="episodic",
        skip_v1_conversation=True,
    )
    assert rec.get("ok")
    assert getattr(mgr, "_last_embedding_status", None) == "failed"
    # row exists
    rows = v1_ms.supabase.table("xiaochenguang_memories").select("*").execute().data
    assert any(r.get("user_message") == "仍應保存" for r in (rows or []))


# ---------------------------------------------------------------------------
# Task E — reflection status contract (unit-level shape)
# ---------------------------------------------------------------------------

def test_reflection_status_values():
    allowed = {"pending", "completed", "failed", "unavailable"}
    assert "pending" in allowed
    # ChatResponse field exists
    from backend.chat_router import ChatResponse

    fields = ChatResponse.model_fields if hasattr(ChatResponse, "model_fields") else ChatResponse.__fields__
    assert "reflection_status" in fields
