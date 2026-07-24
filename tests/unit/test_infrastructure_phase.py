"""Infrastructure Phase unit tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.modules.reflection_contract import (
    normalize_reflection,
    validate_reflection,
    empty_reflection,
)
from backend.modules.token_counter import (
    count_text_tokens,
    account_turn,
    build_usage_record,
    append_token_ledger,
)
from backend.modules.finetune_dataset import (
    build_sft_row,
    validate_dataset,
    dataset_statistics,
    export_jsonl,
    filter_records,
    records_from_memory_rows,
)
from backend.redis_interface import RedisInterface


def test_reflection_contract_normalize_legacy():
    raw = {
        "summary": "太短",
        "improvements": ["加例子", "更溫柔"],
        "causes": ["忽略上下文"],
        "confidence": 0.8,
    }
    n = normalize_reflection(raw)
    ok, msg = validate_reflection(n)
    assert ok, msg
    assert n["summary"] == "太短"
    assert "加例子" in n["lessons"]
    assert n["causes"] == ["忽略上下文"]
    assert 0 <= n["confidence"] <= 1
    assert n["timestamp"]


def test_reflection_contract_from_storage_shape():
    raw = {
        "reflection_content": "內容",
        "confidence_score": 70,  # 0-100 mistaken scale
        "analysis_tags": {"dominant_causes": ["a"], "top_improvements": ["b"]},
    }
    n = normalize_reflection(raw)
    assert n["summary"] == "內容"
    assert n["causes"] == ["a"]
    assert n["lessons"] == ["b"]
    assert n["confidence"] == 0.7


def test_empty_reflection_valid():
    e = empty_reflection()
    ok, _ = validate_reflection(e)
    assert ok


def test_token_counter_basic():
    n = count_text_tokens("你好小宸光 hello")
    assert n > 0
    rec = account_turn(
        user_message="hi",
        assistant_message="hello there",
        model="gpt-4o-mini",
        conversation_id="c1",
        user_id="u1",
    )
    assert rec["prompt_tokens"] >= 0
    assert rec["completion_tokens"] >= 0
    assert rec["total_tokens"] == rec["prompt_tokens"] + rec["completion_tokens"]
    assert "estimated_cost" in rec
    # tokens not inside messages
    assert "hi" not in json.dumps(rec.get("token_ids"))


def test_token_counter_prefers_api_usage():
    rec = account_turn(
        user_message="a",
        assistant_message="b",
        usage_from_api={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )
    assert rec["prompt_tokens"] == 10
    assert rec["source"] == "api_usage"


def test_token_ledger_append(tmp_path):
    rec = build_usage_record(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    p = append_token_ledger(rec, path=tmp_path / "ledger.jsonl")
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_finetune_dataset_export(tmp_path):
    rows = [
        build_sft_row(
            user_message="你好",
            assistant_message="哈尼～",
            reflection={"summary": "ok", "causes": ["c"], "lessons": ["l"], "confidence": 0.5},
            user_id="u1",
            conversation_id="c1",
        )
    ]
    v = validate_dataset(rows)
    assert v["ok"]
    stats = dataset_statistics(rows)
    assert stats["rows"] == 1
    assert stats["with_reflection"] == 1
    out = export_jsonl(rows, tmp_path / "ds.jsonl")
    assert out["ok"]
    assert Path(out["path"]).exists()


def test_finetune_filter_and_from_memory():
    rows = records_from_memory_rows(
        [
            {
                "user_message": "a",
                "assistant_message": "b",
                "user_id": "u1",
                "conversation_id": "c1",
                "created_at": "2026-07-01T00:00:00",
            },
            {
                "user_message": "x",
                "assistant_message": "y",
                "user_id": "u2",
                "conversation_id": "c2",
                "created_at": "2026-07-20T00:00:00",
            },
        ]
    )
    filtered = filter_records(rows, user_id="u1")
    assert len(filtered) == 1


def test_redis_latest_payload_canonical():
    legacy = {
        "user_msg": "hi",
        "assistant_msg": "yo",
        "reflection": {"summary": "s", "causes": ["c"]},
        "user_id": "u",
        "timestamp": 1700000000,
    }
    norm = RedisInterface.normalize_latest_payload(legacy)
    assert "messages" in norm
    assert norm["messages"][0]["role"] == "user"
    assert norm["summary"]
    assert norm["reflection"]["summary"] == "s"
    assert "lessons" in norm["reflection"]
    assert norm["updated_at"]
