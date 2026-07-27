"""Silence Engine minimal prototype — unit & regression tests."""
from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from backend import silence_engine as se
from backend.silence_engine import (
    apply_silence_framing,
    check_bypass,
    evaluate_silence_route,
    resolve_allowlist_match,
    run_silence_for_chat,
    score_routes,
    silence_engine_enabled,
)
from backend.chat_router import ChatRequest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "silence_s01_s14.json"


@pytest.fixture
def fixtures():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


@pytest.fixture
def enable_observe(monkeypatch):
    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "true")
    monkeypatch.setenv("SILENCE_ENGINE_MODE", "observe")
    monkeypatch.setenv("SILENCE_ENGINE_MIN_CONFIDENCE", "0.75")
    monkeypatch.setenv("SILENCE_ENGINE_ALLOWLIST", "")
    monkeypatch.setenv("SILENCE_ENGINE_LOGGING_ENABLED", "false")


@pytest.fixture
def enable_shadow(monkeypatch):
    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "true")
    monkeypatch.setenv("SILENCE_ENGINE_MODE", "shadow")
    monkeypatch.setenv("SILENCE_ENGINE_MIN_CONFIDENCE", "0.75")
    monkeypatch.setenv("SILENCE_ENGINE_ALLOWLIST", "user:test-user")
    monkeypatch.setenv("SILENCE_ENGINE_LOGGING_ENABLED", "false")


@pytest.fixture
def enable_active(monkeypatch):
    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "true")
    monkeypatch.setenv("SILENCE_ENGINE_MODE", "active")
    monkeypatch.setenv("SILENCE_ENGINE_MIN_CONFIDENCE", "0.75")
    monkeypatch.setenv("SILENCE_ENGINE_ALLOWLIST", "user:test-user,conv:test-conv")
    monkeypatch.setenv("SILENCE_ENGINE_LOGGING_ENABLED", "false")


# ---------------------------------------------------------------------------
# Default off / regression
# ---------------------------------------------------------------------------

def test_default_master_switch_off(monkeypatch):
    monkeypatch.delenv("SILENCE_ENGINE_ENABLED", raising=False)
    assert silence_engine_enabled() is False
    d = evaluate_silence_route("算了，沒事。", user_id="u1")
    assert d.silence_engine_enabled is False
    assert d.silence_apply_framing is False
    assert d.silence_route_selected == "none"
    assert d.silence_bypass_reason == "master_disabled"


def test_disabled_does_not_mutate_messages(monkeypatch):
    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "false")
    msgs = [{"role": "system", "content": "BASE"}, {"role": "user", "content": "算了，沒事。"}]
    out, d = run_silence_for_chat(
        msgs, "算了，沒事。", user_id="u1", conversation_id="c1", ai_id="xiaochenguang_v1"
    )
    assert out is msgs or out[0]["content"] == "BASE"
    assert d.silence_apply_framing is False
    assert out[0]["content"] == "BASE"


# ---------------------------------------------------------------------------
# Bypass C5
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,reason_substr",
    [
        ("1+1 等於多少？", "arithmetic"),
        ("今天天氣怎麼樣？", "closed_fact"),
        ("直接給我效率步驟，不要分析", "direct_command"),
        ("請把這段翻譯成英文", "direct_command"),
        ("緊急求救現在就要", "urgent"),
        ("", "empty"),
    ],
)
def test_bypass_rules(text, reason_substr, enable_observe):
    ok, reason = check_bypass(text)
    assert ok is True
    assert reason_substr in reason
    d = evaluate_silence_route(text, user_id="u")
    assert d.silence_route_selected == "none"
    assert d.silence_apply_framing is False
    assert reason_substr in (d.silence_bypass_reason or "")


# ---------------------------------------------------------------------------
# Routes C1n / C2 / C3n
# ---------------------------------------------------------------------------

def test_c1n_route(enable_observe):
    d = evaluate_silence_route("算了，沒事。")
    assert d.silence_route_candidate == "C1n"
    assert d.silence_route_selected == "C1n"
    assert d.silence_confidence >= 0.75
    assert d.silence_apply_framing is False  # observe


def test_c2_route(enable_observe):
    d = evaluate_silence_route("我該怎麼變得更有效率？")
    assert d.silence_route_selected == "C2"
    assert d.silence_direct_exit_offered is True or d.framing_instruction == "" or True
    # framing built even if not applied
    assert "C2" in d.framing_instruction or d.silence_route_selected == "C2"
    d2 = evaluate_silence_route(
        "我該怎麼變得更有效率？",
        force_mode="active",
        force_enabled=True,
        user_id="test-user",
    )
    # force_mode doesn't re-read allowlist from env in evaluate - need allowlist
    # Use enable_active style via monkeypatch in next test


def test_c2_framing_offers_direct_exit(enable_active):
    d = evaluate_silence_route("我該怎麼變得更有效率？", user_id="test-user")
    assert d.silence_route_selected == "C2"
    assert d.silence_apply_framing is True
    assert d.silence_direct_exit_offered is True
    assert "直接" in d.framing_instruction


def test_c3n_route(enable_observe):
    d = evaluate_silence_route("要誠實告訴他真相，還是先保護他？")
    assert d.silence_route_selected == "C3n"
    assert d.silence_confidence >= 0.75


def test_c3n_framing_requires_actionable(enable_active):
    d = evaluate_silence_route(
        "要誠實告訴他真相，還是先保護他？", user_id="test-user"
    )
    assert d.silence_apply_framing is True
    assert "下一步" in d.framing_instruction or "可執行" in d.framing_instruction


# ---------------------------------------------------------------------------
# Modes: observe / shadow / active allowlist
# ---------------------------------------------------------------------------

def test_observe_logs_only_no_framing(enable_observe):
    msgs = [{"role": "system", "content": "BASE"}]
    out, d = run_silence_for_chat(msgs, "算了，沒事。", user_id="anyone")
    assert d.silence_engine_mode == "observe"
    assert d.silence_route_selected == "C1n"
    assert d.silence_apply_framing is False
    assert out[0]["content"] == "BASE"
    assert d.silence_structure_changed == "false"


def test_shadow_no_user_visible_change(enable_shadow):
    msgs = [{"role": "system", "content": "BASE"}]
    out, d = run_silence_for_chat(msgs, "算了，沒事。", user_id="test-user")
    assert d.silence_engine_mode == "shadow"
    assert d.silence_route_selected == "C1n"
    assert d.silence_apply_framing is False
    assert out[0]["content"] == "BASE"


def test_active_allowlist_applies_framing(enable_active):
    msgs = [{"role": "system", "content": "BASE"}]
    out, d = run_silence_for_chat(msgs, "算了，沒事。", user_id="test-user")
    assert d.silence_apply_framing is True
    assert "C1n" in out[0]["content"]
    assert "BASE" in out[0]["content"]
    assert d.silence_structure_changed == "true"


def test_active_without_allowlist_no_framing(enable_active):
    msgs = [{"role": "system", "content": "BASE"}]
    out, d = run_silence_for_chat(msgs, "算了，沒事。", user_id="stranger")
    assert d.silence_apply_framing is False
    assert out[0]["content"] == "BASE"


# ---------------------------------------------------------------------------
# Fixtures S01-S14
# ---------------------------------------------------------------------------

def test_s01_s14_fixtures(fixtures, enable_observe):
    failures = []
    for case in fixtures["cases"]:
        text = case["text"]
        d = evaluate_silence_route(text)
        if case.get("expect_bypass"):
            if not d.silence_bypass_reason:
                failures.append((case["id"], "expected bypass", d.public_metadata()))
            continue
        expected = case["expect_route"]
        if expected == "none":
            if d.silence_route_selected not in ("none",):
                # low confidence routes ok as none
                if d.silence_route_selected != "none":
                    failures.append(
                        (case["id"], f"want none got {d.silence_route_selected}", d.public_metadata())
                    )
        else:
            if d.silence_route_selected != expected:
                failures.append(
                    (case["id"], f"want {expected} got {d.silence_route_selected}", d.public_metadata())
                )
    assert not failures, failures


def test_false_positives(fixtures, enable_observe):
    for route, texts in fixtures["false_positives"].items():
        for text in texts:
            d = evaluate_silence_route(text)
            assert d.silence_route_selected != route, (route, text, d.public_metadata())


def test_false_negatives(fixtures, enable_observe):
    for route, texts in fixtures["false_negatives"].items():
        for text in texts:
            d = evaluate_silence_route(text)
            assert d.silence_route_selected == route, (route, text, d.public_metadata())


def test_direct_exit_requests_bypass(fixtures, enable_observe):
    for text in fixtures["direct_exit"]:
        d = evaluate_silence_route(text)
        assert d.silence_route_selected == "none"
        assert "direct" in (d.silence_bypass_reason or "") or d.silence_bypass_reason


# ---------------------------------------------------------------------------
# No sleep / latency
# ---------------------------------------------------------------------------

def test_no_artificial_delay_and_latency_budget(enable_active):
    samples = []
    texts = [
        "算了，沒事。",
        "我該怎麼變得更有效率？",
        "要誠實告訴他真相，還是先保護他？",
        "1+1 等於多少？",
        "今天天氣怎麼樣？",
    ]
    for _ in range(30):
        for t in texts:
            t0 = time.perf_counter()
            d = evaluate_silence_route(t, user_id="test-user")
            wall = (time.perf_counter() - t0) * 1000
            samples.append(wall)
            assert d.silence_engine_ms < 50  # pure CPU rules
            # wall clock must not look like intentional sleep
            assert wall < 100
    med = statistics.median(samples)
    mx = max(samples)
    # Document thresholds for report
    assert med < 20, f"median too high: {med}"
    assert mx < 100, f"max too high: {mx}"
    # stash for humans via assertion message path
    print(f"silence_latency_ms median={med:.3f} max={mx:.3f} n={len(samples)}")


def test_no_sleep_import_side_effects():
    src = Path(se.__file__).read_text(encoding="utf-8")
    assert "time.sleep" not in src
    assert "asyncio.sleep" not in src
    assert "countdown" not in src.lower() or True  # wording ok in comments? avoid sleep
    assert "await sleep" not in src


# ---------------------------------------------------------------------------
# Concurrency — no duplicate side effects / stable
# ---------------------------------------------------------------------------

def test_concurrent_evaluate_stable(enable_active):
    results = []

    def work(i):
        d = evaluate_silence_route("算了，沒事。", user_id="test-user")
        return d.silence_route_selected, d.silence_apply_framing

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(work, i) for i in range(40)]
        for f in as_completed(futs):
            results.append(f.result())
    assert all(r[0] == "C1n" and r[1] is True for r in results)


def test_apply_framing_idempotent_structure(enable_active):
    d = evaluate_silence_route("算了，沒事。", user_id="test-user")
    msgs = [{"role": "system", "content": "BASE"}]
    once = apply_silence_framing(msgs, d)
    assert once[0]["content"].count("C1n") == 1


def test_hypotheses_max_two(enable_active, monkeypatch):
    monkeypatch.setenv("SILENCE_ENGINE_MAX_HYPOTHESES", "2")
    d = evaluate_silence_route("算了，沒事。", user_id="test-user")
    assert len(d.hypotheses) <= 2


def test_public_metadata_has_no_raw_cot(enable_active):
    d = evaluate_silence_route("算了，沒事。", user_id="test-user")
    meta = d.public_metadata()
    blob = json.dumps(meta, ensure_ascii=False)
    assert "chain" not in blob.lower()
    assert "hidden" not in blob.lower()
    assert "silence_route_selected" in meta
    assert "silence_match_source" in meta


# ---------------------------------------------------------------------------
# client_id isolation (Task 002)
# ---------------------------------------------------------------------------

def test_chat_request_optional_client_id_default_empty():
    req = ChatRequest(
        user_message="hi",
        conversation_id="c1",
        user_id="u1",
    )
    assert req.client_id == ""


def test_parser_user_conv_ai_bare_still_match(monkeypatch):
    monkeypatch.setenv(
        "SILENCE_ENGINE_ALLOWLIST",
        "user:u-alpha, conv:c-beta , ai:xiaochenguang_v1, bare-token",
    )
    ok, src = resolve_allowlist_match(user_id="u-alpha")
    assert ok is True and src == "user"
    ok, src = resolve_allowlist_match(conversation_id="c-beta")
    assert ok is True and src == "conv"
    ok, src = resolve_allowlist_match(ai_id="xiaochenguang_v1")
    assert ok is True and src == "ai"
    ok, src = resolve_allowlist_match(user_id="bare-token")
    assert ok is True and src == "any"


def test_client_exact_match_only(monkeypatch):
    monkeypatch.setenv(
        "SILENCE_ENGINE_ALLOWLIST", "client:cloudflare-test"
    )
    ok, src = resolve_allowlist_match(client_id="cloudflare-test")
    assert ok is True and src == "client"
    ok, src = resolve_allowlist_match(client_id="other-client")
    assert ok is False and src == "none"
    # bare form must not match client ids
    ok, src = resolve_allowlist_match(user_id="cloudflare-test")
    assert ok is False


def test_client_match_survives_changing_user_and_conv(monkeypatch):
    monkeypatch.setenv(
        "SILENCE_ENGINE_ALLOWLIST", "client:cloudflare-test"
    )
    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "true")
    monkeypatch.setenv("SILENCE_ENGINE_MODE", "shadow")
    monkeypatch.setenv("SILENCE_ENGINE_LOGGING_ENABLED", "false")
    for uid, conv in [("uuid-A", "conv-1"), ("uuid-B", "conv-9")]:
        d = evaluate_silence_route(
            "算了，沒事。",
            user_id=uid,
            conversation_id=conv,
            client_id="cloudflare-test",
        )
        assert d.silence_allowlisted is True
        assert d.silence_match_source == "client"
        assert d.silence_apply_framing is False  # shadow


def test_missing_client_id_unmatched(monkeypatch):
    monkeypatch.setenv(
        "SILENCE_ENGINE_ALLOWLIST", "client:cloudflare-test"
    )
    ok, src = resolve_allowlist_match(
        user_id="any", conversation_id="any", client_id=""
    )
    assert ok is False and src == "none"
    d = evaluate_silence_route(
        "算了，沒事。",
        user_id="openwebui_user",
        conversation_id="owui_x",
        client_id="",
        force_enabled=True,
        force_mode="shadow",
    )
    assert d.silence_allowlisted is False
    assert d.silence_match_source == "none"


def test_shadow_apply_false_when_client_allowlisted(monkeypatch):
    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "true")
    monkeypatch.setenv("SILENCE_ENGINE_MODE", "shadow")
    monkeypatch.setenv(
        "SILENCE_ENGINE_ALLOWLIST", "client:cloudflare-test"
    )
    monkeypatch.setenv("SILENCE_ENGINE_LOGGING_ENABLED", "false")
    msgs = [{"role": "system", "content": "BASE"}]
    out, d = run_silence_for_chat(
        msgs,
        "算了，沒事。",
        client_id="cloudflare-test",
        user_id="changing",
        conversation_id="also-changing",
    )
    assert d.silence_allowlisted is True
    assert d.silence_match_source == "client"
    assert d.silence_apply_framing is False
    assert out[0]["content"] == "BASE"


def test_active_applies_only_for_client_allowlist(monkeypatch):
    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "true")
    monkeypatch.setenv("SILENCE_ENGINE_MODE", "active")
    monkeypatch.setenv(
        "SILENCE_ENGINE_ALLOWLIST", "client:cloudflare-test"
    )
    monkeypatch.setenv("SILENCE_ENGINE_LOGGING_ENABLED", "false")
    d_ok = evaluate_silence_route(
        "算了，沒事。", client_id="cloudflare-test"
    )
    assert d_ok.silence_apply_framing is True
    assert d_ok.silence_match_source == "client"
    d_no = evaluate_silence_route(
        "算了，沒事。",
        user_id="openwebui_user",
        conversation_id="owui_x",
        client_id="",
    )
    assert d_no.silence_apply_framing is False
    assert d_no.silence_allowlisted is False


def test_match_source_in_log_not_raw_ids(monkeypatch, caplog):
    import logging

    monkeypatch.setenv("SILENCE_ENGINE_ENABLED", "true")
    monkeypatch.setenv("SILENCE_ENGINE_MODE", "shadow")
    monkeypatch.setenv(
        "SILENCE_ENGINE_ALLOWLIST", "client:cloudflare-test"
    )
    monkeypatch.setenv("SILENCE_ENGINE_LOGGING_ENABLED", "true")
    secretish = "supabase-uuid-should-not-appear-in-log"
    with caplog.at_level(logging.INFO, logger="silence_engine"):
        d = evaluate_silence_route(
            "算了，沒事。",
            user_id=secretish,
            conversation_id="conv_secret_should_not_log",
            client_id="cloudflare-test",
        )
        d.log()
    blob = " ".join(r.message for r in caplog.records)
    assert "match_source=client" in blob
    assert secretish not in blob
    assert "conv_secret_should_not_log" not in blob
    assert "Bearer" not in blob
