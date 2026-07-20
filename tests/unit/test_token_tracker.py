"""backend/token_tracker.py 單元測試"""
import pytest

from backend.token_tracker import (
    TokenTracker,
    estimate_cost_usd,
    usage_from_openai,
)


@pytest.mark.unit
def test_token_accumulation(tmp_token_log, monkeypatch):
    monkeypatch.setenv("USER_DAILY_TOKEN_BUDGET_USD", "10")
    monkeypatch.setenv("DAILY_TOKEN_BUDGET_USD", "100")
    tracker = TokenTracker(storage_path=str(tmp_token_log))
    tracker.user_daily_budget_usd = 10.0
    tracker.daily_budget_usd = 100.0

    tracker.record(
        user_id="u1",
        conversation_id="c1",
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
    )
    tracker.record(
        user_id="u1",
        conversation_id="c1",
        model="gpt-4o-mini",
        prompt_tokens=200,
        completion_tokens=100,
    )
    summary = tracker.get_user_daily_summary("u1")
    assert summary["prompt_tokens"] == 300
    assert summary["completion_tokens"] == 150
    assert summary["total_tokens"] == 450
    assert summary["calls"] == 2
    assert summary["cost_usd"] >= 0


@pytest.mark.unit
def test_daily_summary_and_zero_cost(tmp_token_log, monkeypatch):
    tracker = TokenTracker(storage_path=str(tmp_token_log))
    tracker.user_daily_budget_usd = 5.0
    tracker.daily_budget_usd = 50.0

    row = tracker.record(
        user_id="u_zero",
        conversation_id="c",
        model="omni-moderation-latest",
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=0.0,
    )
    assert row["cost_usd"] == 0.0
    summary = tracker.get_user_daily_summary("u_zero")
    assert summary["cost_usd"] == 0
    assert summary["remaining_usd"] == 5.0


@pytest.mark.unit
def test_budget_exceeded_blocks(tmp_token_log, monkeypatch):
    tracker = TokenTracker(storage_path=str(tmp_token_log))
    tracker.user_daily_budget_usd = 0.000001  # 極小預算
    tracker.daily_budget_usd = 100.0

    tracker.record(
        user_id="u_budget",
        conversation_id="c",
        model="gpt-4o",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    allowed, reason, ctx = tracker.check_budget("u_budget")
    assert allowed is False
    assert "預算" in reason
    assert "user" in ctx


@pytest.mark.unit
def test_unknown_model_safe_default():
    cost = estimate_cost_usd("totally-unknown-model-xyz", 1_000_000, 1_000_000)
    assert cost > 0
    assert isinstance(cost, float)


@pytest.mark.unit
def test_users_isolated(tmp_token_log, monkeypatch):
    tracker = TokenTracker(storage_path=str(tmp_token_log))
    tracker.user_daily_budget_usd = 10.0
    tracker.daily_budget_usd = 100.0

    tracker.record(
        user_id="alice",
        conversation_id="c1",
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    tracker.record(
        user_id="bob",
        conversation_id="c2",
        model="gpt-4o-mini",
        prompt_tokens=10,
        completion_tokens=5,
    )
    a = tracker.get_user_daily_summary("alice")
    b = tracker.get_user_daily_summary("bob")
    assert a["prompt_tokens"] == 1000
    assert b["prompt_tokens"] == 10
    assert a["total_tokens"] != b["total_tokens"]


@pytest.mark.unit
def test_usage_from_openai_dict_and_none():
    assert usage_from_openai(None)["total_tokens"] == 0
    u = usage_from_openai(
        {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33}
    )
    assert u == {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33}


@pytest.mark.unit
def test_budget_ok_when_under_limit(tmp_token_log):
    tracker = TokenTracker(storage_path=str(tmp_token_log))
    tracker.user_daily_budget_usd = 10.0
    tracker.daily_budget_usd = 100.0
    tracker.record(
        user_id="u_ok",
        conversation_id="c",
        model="gpt-4o-mini",
        prompt_tokens=10,
        completion_tokens=10,
    )
    allowed, reason, _ = tracker.check_budget("u_ok")
    assert allowed is True
    assert reason == "ok"
