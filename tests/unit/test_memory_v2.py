"""Memory System V2 — unit tests (classifier, graph, manager, retrieval, night growth)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.modules.memory_classifier import MemoryClassifier
from backend.modules.memory_types import GRAPH_RELATIONS, MEMORY_TYPES
from backend.modules.graph_manager import GraphManager
from backend.modules.retrieval_engine import RetrievalEngine
from backend.modules.memory_manager import MemoryManager, LegacyMemoryAdapter, memory_v2_enabled
from backend.modules.night_growth import NightGrowth
from tests.mocks.mock_supabase import MockSupabase
from tests.mocks.mock_openai import FakeOpenAIClient


@pytest.fixture
def classifier():
    return MemoryClassifier()


@pytest.fixture
def graph(tmp_path):
    g = GraphManager(user_id="u-test", storage_path=str(tmp_path / "g.json"))
    g.clear()
    return g


@pytest.fixture
def v1_ms():
    from modules.memory_system import MemorySystem

    sb = MockSupabase()
    oa = FakeOpenAIClient()
    return MemorySystem(sb, oa, "xiaochenguang_memories", redis_interface=None)


# ---------- Classifier ----------
@pytest.mark.parametrize(
    "user,expected",
    [
        ("你是誰？", "identity"),
        ("什麼是向量資料庫", "semantic"),
        ("還記得我們上次說過的事嗎", "episodic"),
        ("我今天好難過", "emotion"),
        ("因為下雨所以取消", "causal"),
        ("這很重要請記住", "attention"),
        ("你的人格好像變了", "transformation"),
    ],
)
def test_classifier_primary_types(classifier, user, expected):
    r = classifier.classify(
        conversation={"user_message": user, "assistant_message": "ok"}
    )
    assert r.memory_type in MEMORY_TYPES
    assert r.memory_type == expected
    assert 0 <= r.importance <= 1
    assert 0 <= r.confidence <= 1


def test_classifier_reflection_boost(classifier):
    r = classifier.classify(
        conversation={"user_message": "今天過得如何", "assistant_message": "還好"},
        reflection={"confidence": 0.9, "improvements": ["be kinder"]},
    )
    assert r.memory_type in ("reflection", "transformation", "episodic")
    assert r.confidence > 0
    assert isinstance(r.tags, list)


def test_classifier_document_and_tool(classifier):
    r = classifier.classify(
        conversation={"user_message": "看這個", "assistant_message": "收到"},
        document="PDF about quantum physics",
        tool_result="search ok",
    )
    assert r.memory_type in MEMORY_TYPES
    assert "document" in r.tags or "tool" in r.tags


# ---------- Graph ----------
def test_graph_add_and_neighbors(graph):
    e = graph.add_edge("m1", "m2", "supports", meta={"k": 1})
    assert e["relation"] == "supports"
    assert e["id"]
    n = graph.get_neighbors("m1")
    assert len(n) >= 1
    with pytest.raises(ValueError):
        graph.add_edge("a", "b", "invalid_rel")


def test_graph_all_relations(graph):
    for rel in GRAPH_RELATIONS:
        graph.add_edge("s", "t", rel)
    assert len(graph.list_edges()) >= len(GRAPH_RELATIONS)


def test_graph_apply_classification(graph):
    # Phase2: string labels alone do not create edges
    edges = graph.apply_classification_relations(
        "mem-9",
        [{"relation": "causes", "from": "event", "to": "outcome"}],
    )
    assert edges == []
    edges2 = graph.apply_classification_relations(
        "mem-9",
        [{"relation": "causes", "confidence": 0.5}],
        related_memory_ids=["mem-9", "mem-10"],
    )
    assert len(edges2) >= 1


# ---------- Manager ----------
@pytest.mark.asyncio
async def test_manager_save_and_retrieve(v1_ms, tmp_path):
    g = GraphManager(user_id="u1", storage_path=str(tmp_path / "g2.json"))
    mgr = MemoryManager(v1_ms, graph=g)
    out = await mgr.save(
        user_message="我喜歡無糖綠茶",
        bot_response="記住了～",
        conversation_id="conv-1",
        user_id="u1",
        emotion={"dominant_emotion": "joy", "intensity": 0.7},
    )
    assert out["ok"] is True
    assert out["v1_saved"] is True
    assert out["memory_type"] in MEMORY_TYPES
    # V1 conversation row exists
    rows = v1_ms.supabase.table("xiaochenguang_memories").rows
    assert any(r.get("memory_type") == "conversation" for r in rows)

    retrieved = await mgr.retrieve(
        "綠茶", conversation_id="conv-1", user_id="u1", limit=3
    )
    assert "items" in retrieved
    assert "types" in retrieved


@pytest.mark.asyncio
async def test_manager_update_archive_delete(v1_ms, tmp_path):
    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="u1", storage_path=str(tmp_path / "g3.json"))
    )
    await mgr.save(
        user_message="hello",
        bot_response="world",
        conversation_id="c",
        user_id="u1",
    )
    rows = v1_ms.supabase.table("xiaochenguang_memories").rows
    assert rows
    mid = rows[0]["id"]
    up = await mgr.update(mid, fields={"importance_score": 0.99})
    assert up["ok"] is True
    ar = await mgr.archive(mid)
    assert ar["ok"] is True
    # insert another for delete
    await mgr.save(
        user_message="x",
        bot_response="y",
        conversation_id="c2",
        user_id="u1",
        force_type="semantic",
        skip_v1_conversation=True,
    )
    rows = v1_ms.supabase.table("xiaochenguang_memories").rows
    typed = [r for r in rows if r.get("memory_type") == "semantic"]
    assert typed, "expected semantic typed row"
    d = await mgr.delete(typed[0]["id"])
    assert d["ok"] is True


@pytest.mark.asyncio
async def test_legacy_adapter_save_recall(v1_ms, tmp_path):
    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="u1", storage_path=str(tmp_path / "g4.json"))
    )
    legacy = mgr.as_legacy()
    assert isinstance(legacy, LegacyMemoryAdapter)
    await legacy.save_memory(
        "conv-z",
        "記得我嗎",
        "當然",
        {"dominant_emotion": "neutral", "intensity": 0.5},
        user_id="u1",
    )
    text = await legacy.recall_memories("記得", "conv-z", user_id="u1")
    assert isinstance(text, str)
    hist = legacy.get_conversation_history("conv-z", limit=5)
    assert isinstance(hist, str)


# ---------- Retrieval rules ----------
def test_retrieval_infer_types():
    eng = RetrievalEngine(None)
    assert "identity" in eng.infer_types("你是誰")
    assert "semantic" in eng.infer_types("什麼是量子計算")
    assert "episodic" in eng.infer_types("還記得上次嗎")
    assert "emotion" in eng.infer_types("我心情不好")
    assert "reflection" in eng.infer_types("你的人格成長")
    assert "transformation" in eng.infer_types("你的人格成長")


@pytest.mark.asyncio
async def test_retrieval_engine_with_v1(v1_ms):
    eng = RetrievalEngine(v1_ms)
    await v1_ms.save_memory(
        "conv-r",
        "我每週三運動",
        "很棒",
        {"dominant_emotion": "joy", "intensity": 0.6},
        user_id="u1",
    )
    out = await eng.retrieve("運動", conversation_id="conv-r", user_id="u1")
    assert out["formatted"] or out["items"]


# ---------- Night growth ----------
@pytest.mark.asyncio
async def test_night_growth_dry_and_real(v1_ms, tmp_path):
    from backend.modules.identity_engine import IdentityEngine
    from backend.modules.night_growth_safety import NightGrowthExecutionStore

    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="u1", storage_path=str(tmp_path / "ng.json"))
    )
    ng = NightGrowth(
        mgr,
        identity_engine=IdentityEngine(user_id="u1", base_dir=str(tmp_path / "id")),
        execution_store=NightGrowthExecutionStore(base_dir=str(tmp_path / "ng_store")),
    )
    turns = [
        {
            "user_message": "什麼是記憶",
            "assistant_message": "記憶是經驗的凝結",
            "emotion": {"dominant_emotion": "curious", "intensity": 0.4},
        },
        {
            "user_message": "你是誰",
            "assistant_message": "我是小宸光",
            "reflection": {
                "summary": "可更好",
                "causes": ["c"],
                "lessons": ["l"],
                "confidence": 0.8,
                "timestamp": "t",
            },
        },
    ]
    dry = await ng.run_once(user_id="u1", recent_turns=turns, dry_run=True)
    assert dry["steps"]["reflection"]["status"] == "ok"
    assert dry["dry_run"] is True

    real = await ng.run_once(user_id="u1", recent_turns=turns, dry_run=False)
    assert real["steps"]["graph_update"]["status"] == "ok"
    assert "decision_engine" in real["steps"] or "semantic_builder" in real["steps"]


def test_memory_v2_flag_default_off(monkeypatch):
    monkeypatch.delenv("MEMORY_V2_ENABLED", raising=False)
    assert memory_v2_enabled() is False
    monkeypatch.setenv("MEMORY_V2_ENABLED", "true")
    assert memory_v2_enabled() is True


def test_memory_types_helpers():
    from backend.modules.memory_types import clamp01, is_v2_type, MemoryRecord

    assert clamp01(2) == 1.0
    assert clamp01(-1) == 0.0
    assert clamp01("x") == 0.0
    assert is_v2_type("episodic") is True
    assert is_v2_type("conversation") is False
    rec = MemoryRecord(content="c", memory_type="semantic")
    assert rec.to_dict()["memory_type"] == "semantic"


def test_classifier_reflection_keyword(classifier):
    r = classifier.classify(
        conversation={
            "user_message": "我想反思今天的錯誤並改進",
            "assistant_message": "好的我們一起反思",
        }
    )
    assert r.memory_type in ("reflection", "episodic", "transformation")


@pytest.mark.asyncio
async def test_manager_from_clients_and_build_backend(monkeypatch, tmp_path):
    from backend.modules.memory_manager import build_memory_backend, MemoryManager
    from modules.memory_system import MemorySystem

    sb = MockSupabase()
    oa = FakeOpenAIClient()
    monkeypatch.setenv("MEMORY_V2_ENABLED", "false")
    backend = build_memory_backend(sb, oa, "xiaochenguang_memories")
    assert isinstance(backend, MemorySystem)

    monkeypatch.setenv("MEMORY_V2_ENABLED", "true")
    backend2 = build_memory_backend(sb, oa, "xiaochenguang_memories")
    assert isinstance(backend2, LegacyMemoryAdapter)

    mgr = MemoryManager.from_clients(sb, oa, "xiaochenguang_memories")
    assert isinstance(mgr, MemoryManager)


@pytest.mark.asyncio
async def test_manager_update_delete_no_supabase():
    v1 = MagicMock()
    v1.supabase = None
    v1.redis = None
    mgr = MemoryManager(v1, graph=GraphManager(user_id="x"))
    assert (await mgr.update(1, fields={"importance_score": 1}))["ok"] is False
    assert (await mgr.delete(1))["ok"] is False
    assert (await mgr.update(1, fields={"nope": 1}))["ok"] is False


@pytest.mark.asyncio
async def test_manager_update_delete_errors(v1_ms):
    mgr = MemoryManager(v1_ms, graph=GraphManager(user_id="u"))
    # force table update to raise
    bad = MagicMock()
    bad.update.side_effect = RuntimeError("boom")
    v1_ms.supabase.table = MagicMock(return_value=bad)
    # re-assign methods properly
    table = MagicMock()
    chain = MagicMock()
    chain.eq.return_value.execute.side_effect = RuntimeError("fail")
    table.update.return_value = chain
    table.delete.return_value = chain
    v1_ms.supabase.table = MagicMock(return_value=table)
    assert (await mgr.update(1, fields={"importance_score": 0.1}))["ok"] is False
    assert (await mgr.delete(1))["ok"] is False


@pytest.mark.asyncio
async def test_insert_typed_embedding_fail_and_empty(v1_ms, tmp_path):
    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="u", storage_path=str(tmp_path / "e.json"))
    )
    v1_ms.openai_client.embeddings.raise_error = RuntimeError("no emb")
    out = await mgr.save(
        user_message="重要請記住注意力",
        bot_response="好",
        conversation_id="c",
        user_id="u",
        force_type="attention",
        skip_v1_conversation=True,
    )
    assert out["ok"] is True
    empty = await mgr._insert_typed_record(
        memory_type="semantic",
        user_message="",
        assistant_message="",
        conversation_id="c",
        user_id="u",
        importance=0.5,
        confidence=0.5,
        tags=[],
        ai_id="x",
        meta={},
    )
    assert empty is None


@pytest.mark.asyncio
async def test_retrieval_ms_none_and_format_empty():
    eng = RetrievalEngine(None)
    out = await eng.retrieve("q", conversation_id="c")
    assert out["items"] == [] or isinstance(out["items"], list)
    assert eng._format([]) == ""
    assert eng._format([{"memory_type": "x", "content": ""}]) == ""


@pytest.mark.asyncio
async def test_retrieval_v1_fail_and_typed(v1_ms):
    eng = RetrievalEngine(v1_ms)

    async def boom(*a, **k):
        raise RuntimeError("recall down")

    v1_ms.recall_memories = boom
    # seed typed
    v1_ms.supabase.table("xiaochenguang_memories").insert(
        {
            "id": 99,
            "user_message": "量子計算知識",
            "assistant_message": "說明",
            "memory_type": "semantic",
            "user_id": "u1",
            "document_content": "quantum",
            "importance_score": 0.8,
        }
    ).execute()
    out = await eng.retrieve(
        "量子", conversation_id="c", user_id="u1", memory_types=["semantic"]
    )
    assert any(i.get("memory_type") == "semantic" for i in out["items"])


@pytest.mark.asyncio
async def test_night_growth_load_turns(v1_ms, tmp_path):
    from backend.modules.night_growth_safety import NightGrowthExecutionStore

    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="u1", storage_path=str(tmp_path / "n2.json"))
    )
    await v1_ms.save_memory(
        "conv-n",
        "night msg",
        "night reply",
        {"dominant_emotion": "neutral", "intensity": 0.5},
        user_id="u1",
    )
    ng = NightGrowth(
        mgr,
        execution_store=NightGrowthExecutionStore(base_dir=str(tmp_path / "ng_load")),
    )
    turns = await ng._load_recent_turns(user_id="u1", conversation_id="conv-n")
    assert isinstance(turns, list)
    # with turns from DB
    report = await ng.run_once(user_id="u1", conversation_id="conv-n", dry_run=False)
    assert report["steps"]["graph_update"]["status"] == "ok"


def test_graph_redis_and_file_paths(tmp_path):
    # redis present but get/set
    redis_if = MagicMock()
    redis_if.redis = MagicMock()
    redis_if.redis.get.return_value = b'[{"id":"1","source_id":"a","target_id":"b","relation":"supports"}]'
    g = GraphManager(
        redis_interface=redis_if,
        user_id="ur",
        storage_path=str(tmp_path / "gr.json"),
    )
    edges = g.list_edges()
    assert edges
    g.add_edge("x", "y", "updates")
    redis_if.redis.set.assert_called()
    # corrupt file load
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    g2 = GraphManager(user_id="u2", storage_path=str(bad))
    g2._ensure_loaded()
    assert isinstance(g2.list_edges(), list)


def test_graph_redis_load_fail(tmp_path):
    redis_if = MagicMock()
    redis_if.redis = MagicMock()
    redis_if.redis.get.side_effect = RuntimeError("redis down")
    g = GraphManager(
        redis_interface=redis_if,
        user_id="u",
        storage_path=str(tmp_path / "x.json"),
    )
    g._ensure_loaded()
    # persist redis fail
    redis_if.redis.set.side_effect = RuntimeError("set fail")
    g._local_edges = []
    g._loaded = True
    g.add_edge("1", "2", "causes")


@pytest.mark.asyncio
async def test_legacy_emotional_and_history(v1_ms, tmp_path):
    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="u", storage_path=str(tmp_path / "l.json"))
    )
    legacy = mgr.as_legacy()
    await legacy.save_emotional_state(
        "u", {"dominant_emotion": "joy", "intensity": 0.5}, "ctx"
    )
    assert legacy.get_recent_context("nope") is None
    legacy._cache_short_term(
        conversation_id="c",
        user_id="u",
        user_input="a",
        bot_response="b",
    )


@pytest.mark.asyncio
async def test_manager_graph_apply_exception(v1_ms, tmp_path):
    g = GraphManager(user_id="u", storage_path=str(tmp_path / "gx.json"))
    mgr = MemoryManager(v1_ms, graph=g)
    g.apply_classification_relations = MagicMock(side_effect=RuntimeError("gfail"))
    out = await mgr.save(
        user_message="因為所以因果",
        bot_response="了解",
        conversation_id="c",
        user_id="u",
    )
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_insert_typed_no_supabase_and_insert_fail(tmp_path):
    v1 = MagicMock()
    v1.supabase = None
    v1.openai_client = None
    v1.memories_table = "t"
    v1.redis = None
    mgr = MemoryManager(v1, graph=GraphManager(user_id="u", storage_path=str(tmp_path / "z.json")))
    assert await mgr._insert_typed_record(
        memory_type="semantic",
        user_message="a",
        assistant_message="b",
        conversation_id="c",
        user_id="u",
        importance=0.5,
        confidence=0.5,
        tags=[],
        ai_id="x",
        meta={},
    ) is None

    v1.supabase = MagicMock()
    table = MagicMock()
    table.insert.return_value.execute.side_effect = RuntimeError("insert fail")
    v1.supabase.table.return_value = table
    v1.openai_client = FakeOpenAIClient()
    assert await mgr._insert_typed_record(
        memory_type="semantic",
        user_message="a",
        assistant_message="b",
        conversation_id="c",
        user_id="u",
        importance=0.5,
        confidence=0.5,
        tags=[],
        ai_id="x",
        meta={},
    ) is None


@pytest.mark.asyncio
async def test_night_growth_attention_and_graph_fail(v1_ms, tmp_path):
    from backend.modules.identity_engine import IdentityEngine
    from backend.modules.night_growth_safety import NightGrowthExecutionStore

    g = GraphManager(user_id="u1", storage_path=str(tmp_path / "ngf.json"))
    mgr = MemoryManager(v1_ms, graph=g)
    ng = NightGrowth(
        mgr,
        identity_engine=IdentityEngine(user_id="u1", base_dir=str(tmp_path / "id2")),
        execution_store=NightGrowthExecutionStore(base_dir=str(tmp_path / "ng_store2")),
    )
    turns = [
        {
            "user_message": "這很重要請記住注意力焦點",
            "assistant_message": "好的重點記下了",
            "emotion": {"dominant_emotion": "neutral", "intensity": 0.9},
        }
    ]

    def boom(*a, **k):
        raise RuntimeError("edge fail")

    g.add_edge = boom
    rep = await ng.run_once(user_id="u1", recent_turns=turns, dry_run=False)
    assert rep["steps"]["attention_update"]["status"] == "ok"


@pytest.mark.asyncio
async def test_night_growth_load_fail():
    v1 = MagicMock()
    v1.supabase = MagicMock()
    v1.supabase.table.side_effect = RuntimeError("db down")
    v1.redis = None
    mgr = MemoryManager(v1, graph=GraphManager(user_id="u"))
    ng = NightGrowth(mgr)
    turns = await ng._load_recent_turns(user_id="u", conversation_id=None)
    assert turns == []


@pytest.mark.asyncio
async def test_retrieval_graph_neighbors_and_type_skip(v1_ms, tmp_path):
    g = GraphManager(user_id="u1", storage_path=str(tmp_path / "rg.json"))
    g.add_edge("1001", "1002", "supports")
    eng = RetrievalEngine(v1_ms, graph_manager=g)
    out = await eng.retrieve("還記得", conversation_id="c", user_id="u1")
    assert "graph_edges" in out or "items" in out
    # invalid type in list skipped
    out2 = await eng.retrieve(
        "x", conversation_id="c", user_id="u1", memory_types=["not_a_type", "episodic"]
    )
    assert "episodic" in out2["types"] or out2["items"] is not None


def test_graph_file_dict_and_cap(tmp_path):
    path = tmp_path / "cap.json"
    path.write_text('{"u1": [{"id":"old","source_id":"a","target_id":"b","relation":"supports"}]}', encoding="utf-8")
    g = GraphManager(user_id="u1", storage_path=str(path))
    assert g.list_edges()
    # cap path: fill many edges
    g._local_edges = [
        {"id": str(i), "source_id": "s", "target_id": "t", "relation": "supports"}
        for i in range(5001)
    ]
    g._loaded = True
    g.add_edge("n1", "n2", "updates")
    assert len(g._local_edges) <= 5001


def test_graph_apply_invalid_relation_skipped(graph):
    created = graph.apply_classification_relations(
        "m1",
        [
            {"relation": "not_real"},
            {"relation": "supports", "source_memory_id": "m1", "target_memory_id": "m2"},
        ],
    )
    assert len(created) == 1


@pytest.mark.asyncio
async def test_legacy_recall_falls_back_items(v1_ms, tmp_path):
    mgr = MemoryManager(
        v1_ms, graph=GraphManager(user_id="u", storage_path=str(tmp_path / "lf.json"))
    )
    legacy = mgr.as_legacy()

    async def fake_retrieve(*a, **k):
        return {
            "formatted": "",
            "items": [
                {"memory_type": "conversation", "content": "【喚醒記憶】\n- test"}
            ],
        }

    mgr.retrieve = fake_retrieve
    text = await legacy.recall_memories("q", "c", "u")
    assert "喚醒記憶" in text or "test" in text
