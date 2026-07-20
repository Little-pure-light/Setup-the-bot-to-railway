"""未授權請求必須帶 X-Request-ID 與 body.request_id（非 null）。"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_unauthorized_response_has_request_id_header_and_body(monkeypatch):
    monkeypatch.setenv("API_SECRET", "test-secret-for-auth")
    # 重新讀取 main 的 API_SECRET 模組變數
    import main as main_mod

    main_mod.API_SECRET = "test-secret-for-auth"

    with TestClient(main_mod.app) as client:
        r = client.get("/api/memories/test-conv")
    assert r.status_code == 401
    rid_header = r.headers.get("X-Request-ID")
    assert rid_header
    assert len(rid_header) >= 8
    body = r.json()
    assert body.get("detail") == "Unauthorized"
    assert body.get("request_id") is not None
    assert body.get("request_id") != ""
    assert body.get("request_id") == rid_header


@pytest.mark.integration
def test_unauthorized_respects_incoming_request_id(monkeypatch):
    monkeypatch.setenv("API_SECRET", "test-secret-for-auth")
    import main as main_mod

    main_mod.API_SECRET = "test-secret-for-auth"
    incoming = "client-rid-abc12345"

    with TestClient(main_mod.app) as client:
        r = client.post(
            "/api/chat?stream=false",
            json={
                "user_message": "hi",
                "conversation_id": "c1",
                "user_id": "u1",
            },
            headers={"X-Request-ID": incoming},
        )
    assert r.status_code == 401
    assert r.headers.get("X-Request-ID") == incoming
    assert r.json().get("request_id") == incoming


@pytest.mark.integration
def test_authorized_with_api_secret_passes_auth_gate(monkeypatch):
    """帶正確 Bearer 不應在 auth 層被 401（後續可能 4xx/5xx 因 mock 環境）。"""
    monkeypatch.setenv("API_SECRET", "test-secret-for-auth")
    import main as main_mod

    main_mod.API_SECRET = "test-secret-for-auth"

    with TestClient(main_mod.app) as client:
        r = client.get(
            "/api/health",
            headers={"Authorization": "Bearer test-secret-for-auth"},
        )
    # health 在豁免路徑；用另一受保護路徑測成功通過 auth
    with TestClient(main_mod.app) as client:
        r = client.get(
            "/api/tools",
            headers={"Authorization": "Bearer test-secret-for-auth"},
        )
    assert r.status_code != 401
    assert r.headers.get("X-Request-ID")
