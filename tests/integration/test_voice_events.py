"""
Task008-002（Round2）— voice event DB telemetry 明確停用。
POST /api/voice/events 維持相容 200，合法 event 一律回 recorded=false, storage_status=disabled；
不讀 env、不 import/呼叫 Supabase、不持久化任何內容。語音/朗讀/車載不受影響。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

MARKER = "VOICE_PRIVATE_MARKER_must_not_persist_or_call"


def _client():
    from backend.voice_router import router
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_valid_event_disabled_and_zero_supabase_call(monkeypatch):
    # 即使環境設定了表名，也必須停用、零 Supabase call（env 無關）
    monkeypatch.setenv("SUPABASE_VOICE_EVENTS_TABLE", "voice_events")
    import backend.supabase_handler as sh
    gs = MagicMock()
    monkeypatch.setattr(sh, "get_supabase", gs)
    r = _client().post(
        "/api/voice/events",
        json={"event_type": "speak_start", "transcript": MARKER, "detail": {"note": MARKER}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["recorded"] is False
    assert body["storage_status"] == "disabled"
    # 零 Supabase 呼叫；response 不含私人內容
    assert gs.call_count == 0
    assert MARKER not in r.text


def test_disabled_also_when_env_unset(monkeypatch):
    monkeypatch.delenv("SUPABASE_VOICE_EVENTS_TABLE", raising=False)
    import backend.supabase_handler as sh
    gs = MagicMock()
    monkeypatch.setattr(sh, "get_supabase", gs)
    r = _client().post("/api/voice/events", json={"event_type": "listen_start"})
    assert r.status_code == 200
    assert r.json()["storage_status"] == "disabled"
    assert gs.call_count == 0


def test_no_supabase_import_triggered_by_endpoint(monkeypatch):
    """端點不得載入 supabase_handler.get_supabase（telemetry 停用 → 不 import/call）。"""
    import backend.supabase_handler as sh
    called = {"n": 0}
    def boom():
        called["n"] += 1
        raise AssertionError("get_supabase must not be called")
    monkeypatch.setattr(sh, "get_supabase", boom)
    r = _client().post("/api/voice/events", json={"event_type": "car_mode_on"})
    assert r.status_code == 200
    assert called["n"] == 0


def test_bad_event_type_400(monkeypatch):
    r = _client().post("/api/voice/events", json={"event_type": "not-real"})
    assert r.status_code == 400


def test_route_mounted_on_real_app_openapi():
    """真實 main.app / OpenAPI 邊界：確認 /api/voice/events 仍掛載（相容 200，非 404）。"""
    import main as m
    paths = m.app.openapi().get("paths", {})
    assert "/api/voice/events" in paths
    assert "post" in paths["/api/voice/events"]
