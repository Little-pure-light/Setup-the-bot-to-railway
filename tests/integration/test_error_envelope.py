"""
Task008-003 — 統一錯誤 envelope 與去敏（真實 handler / 真實 main.app）。
envelope: success/error_code/message/trace_id（保留 detail 與 request_id 向後相容，
但 detail 只放中央安全訊息，5xx 省略 detail、絕不回原 exc.detail）。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.testclient import TestClient

# 於 runtime 組出「看似敏感」字串，避免在原始檔留下真金鑰樣式（不觸發 secret scan）
PRIV = "PRIVATE-" + "sk" + "-" + ("A" * 24)
INTERNAL_PATH = "/internal/admin/secret-key-store"
BEARER = "Bearer " + "eyJ" + ("A" * 24) + "." + ("B" * 12) + "." + ("C" * 12)
LEAK = f"{PRIV} at {INTERNAL_PATH} token={BEARER}"


def _assert_envelope(j, expected_code=None):
    for k in ("success", "error_code", "message", "trace_id"):
        assert k in j, f"envelope 缺少欄位 {k}"
    assert j["success"] is False
    assert isinstance(j["error_code"], str) and j["error_code"]
    assert isinstance(j["message"], str) and j["message"]
    assert j["trace_id"]
    if expected_code:
        assert j["error_code"] == expected_code


def _handler_app():
    """以真實 main handler 函式註冊到受控 app（可加入會拋錯的測試路由）。"""
    import main as m
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, m._http_exception_handler)
    app.add_exception_handler(HTTPException, m._http_exception_handler)
    app.add_exception_handler(RequestValidationError, m._validation_exception_handler)
    app.add_exception_handler(Exception, m._unhandled_exception_handler)

    @app.get("/boom400")
    async def boom400():
        raise HTTPException(status_code=400, detail=LEAK)

    @app.get("/boom500")
    async def boom500():
        raise RuntimeError(LEAK)

    return app


def test_status_to_error_code_and_message_mapping():
    import main as m
    expect = {400: "BAD_REQUEST", 401: "AUTH_ERROR", 403: "FORBIDDEN", 404: "NOT_FOUND",
              409: "CONFLICT", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED", 500: "INTERNAL_ERROR"}
    for code, ec in expect.items():
        body, rid = m._error_envelope(code)
        assert body["error_code"] == ec and body["success"] is False and body["message"]
        assert body["trace_id"] == rid and body["request_id"] == rid


def test_400_http_exception_does_not_leak_detail():
    with TestClient(_handler_app()) as c:
        r = c.get("/boom400")
    assert r.status_code == 400
    j = r.json()
    _assert_envelope(j, "BAD_REQUEST")
    # 絕不回原 exc.detail
    assert PRIV not in r.text and INTERNAL_PATH not in r.text and "Bearer" not in r.text
    assert j.get("message") != LEAK
    if "detail" in j:
        assert j["detail"] != LEAK


def test_500_unhandled_exception_desensitized_response_and_log(caplog, monkeypatch):
    # 即使開啟 verbose，也不得洩漏 marker/內部路徑/秘密樣式
    monkeypatch.setenv("LOG_VERBOSE_EXCEPTIONS", "true")
    with caplog.at_level("DEBUG"):
        with TestClient(_handler_app(), raise_server_exceptions=False) as c:
            r = c.get("/boom500")
    assert r.status_code == 500
    j = r.json()
    _assert_envelope(j, "INTERNAL_ERROR")
    # response 與 log 均不得含原始例外文字/秘密樣式/內部路徑
    assert PRIV not in r.text and INTERNAL_PATH not in r.text and "Bearer" not in r.text
    assert "detail" not in j  # 5xx 省略 detail
    assert PRIV not in caplog.text and INTERNAL_PATH not in caplog.text and "Bearer" not in caplog.text


def test_unknown_route_404_envelope(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "API_SECRET", "")
    with TestClient(m.app) as c:
        r = c.get("/api/definitely-not-a-real-route-xyz")
    assert r.status_code == 404
    _assert_envelope(r.json(), "NOT_FOUND")
    assert r.headers.get("X-Request-ID")


def test_validation_422_envelope_desensitized(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "API_SECRET", "")
    with TestClient(m.app) as c:
        r = c.post("/api/archive_conversation", json={"user_id": "leak-check-value-xyz"})
    assert r.status_code == 422
    j = r.json()
    _assert_envelope(j, "VALIDATION_ERROR")
    detail = j.get("detail")
    if isinstance(detail, list):
        for e in detail:
            assert set(e.keys()) <= {"loc", "type", "msg"}
            assert "input" not in e
    assert "leak-check-value-xyz" not in r.text


def test_auth_401_envelope_backward_compatible(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "API_SECRET", "test-secret-envelope")
    with TestClient(m.app) as c:
        r = c.get("/api/memories/some-conv")
    assert r.status_code == 401
    j = r.json()
    _assert_envelope(j, "AUTH_ERROR")
    assert j.get("detail") == "Unauthorized"           # 相容
    assert j.get("request_id") == j.get("trace_id")     # 相容
    assert r.headers.get("X-Request-ID") == j.get("trace_id")


def test_route_level_http_exception_wrapped(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "API_SECRET", "")
    with TestClient(m.app) as c:
        r = c.post("/api/archive_conversation", json={"conversation_id": "c-1"})
    assert r.status_code == 401
    _assert_envelope(r.json(), "AUTH_ERROR")
    # 原始 detail「缺少 Authorization header」不得外洩
    assert "Authorization header" not in r.text
