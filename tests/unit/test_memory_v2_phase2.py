"""Memory V2 Phase 2 — identity, semantic, decision, scheduler, graph memory_id, night v2."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.modules.identity_engine import IdentityEngine, DEFAULT_IDENTITY
from backend.modules.semantic_builder import SemanticBuilder
from backend.modules.decision_engine import DecisionEngine
from backend.modules.scheduler import GrowthScheduler
from backend.modules.graph_manager import GraphManager
from backend.modules.night_growth import NightGrowth
from backend.modules.memory_manager import MemoryManager
from backend.modules.retrieval_engine import RetrievalEngine, _cosine
from modules.memory_system import MemorySystem
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_openai import FakeOpenAIClient


@pytest.fixture
def v1_ms():
    return MemorySystem(MockSupabase(), FakeOpenAIClient(), "xiaochenguang_memories")


def test_identity_versioning_and_rollback(tmp_path):
    eng = IdentityEngine(
        user_id="u-id",
        base_dir=str(tmp_path / "id"),
        update_mode="formal",
    )
    a = eng.load()
    assert a["version"] == 1
    assert a["role"]
    b = eng.update(
        {"mission": ["新使命"]},
        change_reason="test",
        confidence=0.9,
        source="unit_test",
        force_formal=True,
    )
    assert b["status"] == "formal"
    assert b["charter"]["version"] == 2
    assert "新使命" in b["charter"]["mission"]
    assert 1 in eng.list_versions() and 2 in eng.list_versions()
    c = eng.rollback(1)
    assert c["status"] == "formal"
    assert c["charter"]["version"] == 3
    assert "小宸光" in c["charter"]["role"] or c["charter"]["role"]
    exp = eng.export()
    assert exp.exists()
    frag = eng.to_prompt_fragment()
    assert "Identity" in frag or "Role" in frag


def test_semantic_builder_no_full_chat_dump():
    sb = SemanticBuilder()
    long_chat = "哈尼～" * 50 + "今天天氣不錯我們來聊天吧嘿嘿"
    items = sb.generate_semantic_memory(
        user_message="我喜歡無糖綠茶",
        assistant_message=long_chat,
        reflection={
            "summary": "可更具體",
            "causes": ["太泛"],
            "lessons": ["下次舉例"],
            "confidence": 0.7,
            "timestamp": "t",
        },
    )
    # preference or lesson extracted (not full chat dump)
    assert items, "expected some semantic items"
    assert any(
        ("綠茶" in (i.get("text") or "")) or (i.get("kind") in ("lesson", "preference", "cause"))
        for i in items
    )
    # must not store full assistant dump as single knowledge blob equal to full chat
    assert not any(i.get("text") == long_chat for i in items)
    merged = sb.merge_similar(items + items)
    assert len(merged) <= len(items)


def test_decision_engine_rules():
    de = DecisionEngine()
    d1 = de.decide(user_message="hi", assistant_message="yo")
    assert d1.forget or not d1.save
    d2 = de.decide(
        user_message="你是誰",
        assistant_message="我是小宸光",
        classification={"memory_type": "identity", "confidence": 0.9, "importance": 0.8, "tags": ["identity_query"]},
    )
    assert d2.save and d2.update_identity
    d3 = de.decide(
        user_message="記得重點",
        assistant_message="好",
        classification={"memory_type": "attention", "importance": 0.8, "confidence": 0.7, "tags": ["attention"]},
    )
    assert d3.update_attention
    d4 = de.decide(
        user_message="知識",
        assistant_message="定義是...",
        semantic_items=[{"text": "fact"}],
        classification={"memory_type": "semantic", "importance": 0.6, "confidence": 0.6},
    )
    assert d4.form_long_term_knowledge


def test_scheduler_tick():
    s = GrowthScheduler()
    calls = {"n": 0}

    def job():
        calls["n"] += 1

    s.register("j1", 1.0, job)
    ran = s.tick(now=1000)
    assert "j1" in ran
    assert calls["n"] == 1
    # not due yet
    ran2 = s.tick(now=1000.5)
    assert ran2 == []
    ran3 = s.tick(now=1002)
    assert "j1" in ran3
    assert any(j["name"] == "j1" for j in s.list_jobs())


def test_graph_requires_memory_ids(tmp_path):
    g = GraphManager(user_id="u", storage_path=str(tmp_path / "g.json"))
    g.clear()
    with pytest.raises(ValueError):
        g.add_edge("reflection", "document", "supports")
    e = g.add_edge("101", "202", "causes", confidence=0.9)
    assert e["source_memory_id"] == "101"
    assert e["target_memory_id"] == "202"
    assert "confidence" in e and "timestamp" in e
    # classification string labels alone → no edges without related ids
    created = g.apply_classification_relations(
        "101", [{"relation": "supports", "from": "reflection", "to": "document"}]
    )
    assert created == []
    created2 = g.apply_classification_relations(
        "101",
        [{"relation": "derived_from", "confidence": 0.5}],
        related_memory_ids=["101", "303"],
    )
    assert len(created2) >= 1


@pytest.mark.asyncio
async def test_retrieval_embedding_path(v1_ms, tmp_path):
    # seed typed row with embedding from fake client
    emb = v1_ms.openai_client.embeddings.create(model="text-embedding-3-small", input="綠茶")
    vec = emb.data[0].embedding
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "user_message": "我喜歡無糖綠茶",
            "assistant_message": "記下了",
            "memory_type": "semantic",
            "user_id": "u1",
            "document_content": "pref",
            "embedding": vec,
            "importance_score": 0.8,
        }
    ).execute()
    eng = RetrievalEngine(v1_ms, graph_manager=GraphManager(user_id="u1", storage_path=str(tmp_path / "rg.json")))
    out = await eng.retrieve("綠茶", conversation_id="c", user_id="u1", memory_types=["semantic"])
    assert out["used_embedding"] is True
    assert any(i.get("memory_type") == "semantic" for i in out["items"])


def test_cosine_helper():
    assert _cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert _cosine([1, 0], [0, 1]) == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_night_growth_v2_with_decision(v1_ms, tmp_path):
    from backend.modules.night_growth_safety import NightGrowthExecutionStore

    g = GraphManager(user_id="u1", storage_path=str(tmp_path / "ng.json"))
    mgr = MemoryManager(v1_ms, graph=g)
    ng = NightGrowth(
        mgr,
        identity_engine=IdentityEngine(user_id="u1", base_dir=str(tmp_path / "id")),
        execution_store=NightGrowthExecutionStore(base_dir=str(tmp_path / "ng_store")),
    )
    turns = [
        {
            "user_message": "我喜歡無糖綠茶，這很重要請記住",
            "assistant_message": "好的，我記住你喜歡無糖綠茶",
            "reflection": {
                "summary": "可更確認偏好",
                "causes": ["資訊新"],
                "lessons": ["記錄飲食偏好"],
                "confidence": 0.8,
                "timestamp": "t",
            },
        },
        {
            "user_message": "hi",
            "assistant_message": "yo",
        },
    ]
    dry = await ng.run_once(user_id="u1", recent_turns=turns, dry_run=True)
    assert dry["version"] == "night_growth_v2"
    assert dry["steps"]["decision_engine"]["status"] == "ok"

    real = await ng.run_once(user_id="u1", recent_turns=turns, dry_run=False)
    assert real["steps"]["semantic_builder"]["status"] == "ok"
    assert "graph_update" in real["steps"]
    # scheduler interface exists
    sched = ng.register_scheduler(interval_seconds=3600, user_id="u1")
    assert any(j["name"] == "night_growth_daily" for j in sched.list_jobs())
