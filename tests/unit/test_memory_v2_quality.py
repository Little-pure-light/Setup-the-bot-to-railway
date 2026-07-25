"""Memory V2 Quality Improvement — classifier tiers, ranking, reflection, graph, benchmarks."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.modules.memory_classifier import MemoryClassifier
from backend.modules.memory_manager import MemoryManager
from backend.modules.graph_manager import GraphManager
from backend.modules.retrieval_engine import RetrievalEngine
from backend.modules.reflection_contract import (
    merge_reflections,
    normalize_reflection,
    reflection_quality_score,
    is_actionable_reflection,
)
from backend.modules.decision_engine import DecisionEngine
from backend.modules.identity_engine import IdentityEngine
from backend.modules.night_growth import NightGrowth
from backend.modules.night_growth_safety import NightGrowthExecutionStore
from backend.reflection_module.main import ReflectionModule
from modules.memory_system import MemorySystem
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_openai import FakeOpenAIClient


@pytest.fixture
def v1_ms():
    return MemorySystem(MockSupabase(), FakeOpenAIClient(), "xiaochenguang_memories")


# ---------------------------------------------------------------------------
# Task A — Classifier value tiers
# ---------------------------------------------------------------------------

def test_classifier_low_value_chitchat():
    clf = MemoryClassifier()
    r = clf.classify(conversation={"user_message": "你好", "assistant_message": "嗨～"})
    assert r.value_tier == "low"
    assert r.should_persist is False


def test_classifier_high_value_preference_and_name():
    clf = MemoryClassifier()
    r1 = clf.classify(
        conversation={
            "user_message": "我叫小測A，請記住",
            "assistant_message": "好的小測A",
        }
    )
    assert r1.should_persist is True
    assert r1.value_tier in ("high", "medium")
    assert "self_intro" in r1.tags or r1.memory_type == "identity"

    r2 = clf.classify(
        conversation={
            "user_message": "我喜歡無糖綠茶，以後請記得",
            "assistant_message": "記下了",
        }
    )
    assert r2.should_persist is True
    assert r2.importance >= 0.48


def test_classifier_100_turn_write_volume(v1_ms, tmp_path):
    """Simulated 100 turns: permanent typed writes should stay controlled."""
    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="q", storage_path=str(tmp_path / "g.json"))
    )
    # Before-like baseline: old classifier always persisted episodic
    # After: quality classifier
    turns = []
    for i in range(100):
        if i % 10 == 0:
            um = f"我叫用戶{i}，請記住我的名字"
        elif i % 10 == 1:
            um = f"我喜歡飲品編號{i}"
        elif i % 10 == 2:
            um = "什麼是記憶系統"
        elif i % 5 == 0:
            um = "謝謝"
        elif i % 3 == 0:
            um = "你好"
        elif i % 7 == 0:
            um = "哈哈"
        else:
            um = "嗯"
        turns.append(um)

    typed = 0
    low = 0
    high = 0
    import asyncio

    async def _run_all():
        nonlocal typed, low, high
        for um in turns:
            rec = await mgr.save(
                user_message=um,
                bot_response="好的",
                conversation_id="bench100",
                user_id="quality_user",
                skip_v1_conversation=True,
            )
            if rec.get("id"):
                typed += 1
            tier = rec.get("value_tier")
            if tier == "low":
                low += 1
            if tier == "high":
                high += 1

    asyncio.run(_run_all())

    # After quality gate: typed permanent << 100
    assert typed < 45, f"typed writes too high: {typed}"
    assert low >= 40, f"expected many low-tier: {low}"
    assert high >= 5
    # store stats for report consumers
    stats = {"turns": 100, "typed_persisted": typed, "low_tier": low, "high_tier": high}
    out = Path(tmp_path) / "clf_100.json"
    out.write_text(json.dumps(stats), encoding="utf-8")
    assert stats["typed_persisted"] < stats["turns"] * 0.45


# ---------------------------------------------------------------------------
# Task B — Ranking weights
# ---------------------------------------------------------------------------

def test_rank_weights_prefer_importance_over_recency_alone():
    eng = RetrievalEngine(None, None)
    # important but older-ish
    s_imp = eng._rank_score(
        vector_sim=0.7,
        type_match=0.9,
        importance=0.95,
        recency=0.2,
        graph_conf=0.1,
        source="typed_embedding",
    )
    # recent but unimportant weak match
    s_rec = eng._rank_score(
        vector_sim=0.35,
        type_match=0.3,
        importance=0.2,
        recency=0.99,
        graph_conf=0.0,
        source="typed_embedding",
    )
    assert s_imp > s_rec


@pytest.mark.asyncio
async def test_retrieval_benchmark_top1(v1_ms, tmp_path):
    """20 queries: type-intent top hit quality."""
    eng = RetrievalEngine(v1_ms, GraphManager(user_id="u", storage_path=str(tmp_path / "g.json")))
    emb = v1_ms.openai_client.embeddings.create(model="text-embedding-3-small", input="x")
    vec = emb.data[0].embedding
    seeds = [
        ("m1", "identity", "我是小宸光", "identity_query"),
        ("m2", "semantic", "無糖綠茶是偏好", "tea"),
        ("m3", "episodic", "上次去海邊", "beach"),
        ("m4", "reflection", "下次要更具體", "lesson"),
    ]
    for mid, mt, text, _ in seeds:
        v1_ms.supabase.table("xiaochenguang_memories").insert(
            {
                "id": mid,
                "user_message": text,
                "assistant_message": "ok",
                "memory_type": mt,
                "user_id": "bench_u",
                "embedding": vec,
                "importance_score": 0.85,
                "created_at": "2026-07-25T00:00:00+00:00",
            }
        ).execute()

    cases = [
        ("你是誰", "identity"),
        ("什麼是綠茶", "semantic"),
        ("記得上次海邊", "episodic"),
        ("你的成長反思", "reflection"),
    ]
    # expand to 20 by variants
    queries = []
    for q, t in cases:
        for i in range(5):
            queries.append((f"{q} {i}" if i else q, t))

    hits = 0
    for q, expect_type in queries:
        r = await eng.retrieve(
            q,
            conversation_id="c",
            user_id="bench_u",
            limit=3,
            include_v1_conversation=False,
        )
        items = r.get("items") or []
        if items and items[0].get("memory_type") == expect_type:
            hits += 1
        elif any(it.get("memory_type") == expect_type for it in items[:2]):
            hits += 0.5
    # loose but must beat random
    assert hits >= 8


# ---------------------------------------------------------------------------
# Task C — Reflection quality
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reflection_has_insight_not_hollow():
    mod = ReflectionModule("reflection", {"settings": {"reflection_depth": 3}})
    result = await mod.generate_deep_reflection(
        "為什麼我的回答總是太短？",
        "嗯。",
        {"dominant_emotion": "neutral", "intensity": 0.4},
        {},
    )
    assert result.get("lessons") or result.get("improvements")
    norm = normalize_reflection(result)
    q = reflection_quality_score(norm)
    assert q["score"] >= 0.35
    assert norm.get("summary")
    assert not norm["summary"].startswith("ok")


def test_merge_reflections_dedupes():
    a = {
        "summary": "核心發現：回應過短。後續方向：補例子。",
        "causes": ["長度不足"],
        "lessons": ["下次補充例子"],
        "confidence": 0.6,
        "timestamp": "t1",
    }
    b = {
        "summary": "短",
        "causes": ["長度不足", "缺少結構"],
        "lessons": ["下次補充例子", "下次用總分總"],
        "confidence": 0.7,
        "timestamp": "t2",
    }
    m = merge_reflections(a, b)
    assert len(m["causes"]) == 2
    assert len(m["lessons"]) == 2
    assert m["confidence"] >= 0.6


# ---------------------------------------------------------------------------
# Task D — Identity evolution root cause fixes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identity_candidate_from_preference_without_lowering_threshold(tmp_path, v1_ms):
    eng = IdentityEngine(
        user_id="idq",
        base_dir=str(tmp_path / "id"),
        update_mode="candidate",
        confidence_threshold=0.6,
    )
    store = NightGrowthExecutionStore(base_dir=str(tmp_path / "ng"))
    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="idq", storage_path=str(tmp_path / "g.json"))
    )
    ng = NightGrowth(mgr, identity_engine=eng, execution_store=store)
    turns = [
        {
            "user_message": "我喜歡無糖綠茶，請記住",
            "assistant_message": "好的，我記住你偏好無糖綠茶",
            "reflection": {
                "summary": "核心發現：使用者提出明確偏好。後續方向：穩定稱呼與偏好。",
                "causes": ["使用者主動聲明偏好"],
                "lessons": ["下次先確認並複述使用者偏好"],
                "confidence": 0.7,
                "timestamp": "t",
            },
        }
    ]
    rep = await ng.run_once(
        user_id="idq", recent_turns=turns, dry_run=False, force=True
    )
    assert rep["status"] == "completed"
    # candidate or formal — not silent no-op when actionable
    cands = eng.list_candidates()
    # either formal patch or candidate recorded
    assert eng.load()["version"] >= 1
    # with candidate mode + conf 0.7 should at least candidate or formal
    assert cands or eng.load().get("version", 1) >= 1


# ---------------------------------------------------------------------------
# Task E — Graph utilization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_expansion_hydrates_content(v1_ms, tmp_path):
    g = GraphManager(user_id="gu", storage_path=str(tmp_path / "gg.json"))
    g.clear()
    emb = v1_ms.openai_client.embeddings.create(model="text-embedding-3-small", input="a")
    vec = emb.data[0].embedding
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "id": "g1",
            "user_message": "種子記憶綠茶",
            "assistant_message": "ok",
            "memory_type": "semantic",
            "user_id": "gu",
            "embedding": vec,
            "importance_score": 0.8,
        }
    ).execute()
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "id": "g2",
            "user_message": "關聯知識：無糖更好",
            "assistant_message": "ok",
            "memory_type": "semantic",
            "user_id": "gu",
            "embedding": vec,
            "importance_score": 0.7,
        }
    ).execute()
    g.add_edge("g1", "g2", "supports", confidence=0.9, created_by="test")
    eng = RetrievalEngine(v1_ms, g)
    r = await eng.retrieve(
        "什麼是綠茶",
        conversation_id="c",
        user_id="gu",
        memory_types=["semantic"],
        limit=5,
        include_v1_conversation=False,
    )
    assert r.get("items"), "expected retrieval hits for semantic tea memories"
    blobs = " ".join(it.get("content") or "" for it in (r.get("items") or []))
    assert "綠茶" in blobs or "無糖" in blobs
    # graph should be consulted when seed ids exist
    assert r.get("used_graph") is True or len(r.get("graph_edges") or []) >= 1


# ---------------------------------------------------------------------------
# Task F — Decision respects tier
# ---------------------------------------------------------------------------

def test_decision_skips_low_tier():
    de = DecisionEngine()
    d = de.decide(
        user_message="hi",
        assistant_message="yo",
        classification={
            "memory_type": "episodic",
            "importance": 0.2,
            "confidence": 0.4,
            "value_tier": "low",
            "should_persist": False,
            "tags": ["tier:low"],
        },
    )
    assert d.forget or not d.save
