"""Debug API 鎖定"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("KERNEL_DEBUG_ENABLED", "true")
    monkeypatch.setenv("API_SECRET", "debug-secret-xyz")
    monkeypatch.delenv("KERNEL_DEBUG_SECRET", raising=False)
    from backend.ai_kernel import debug_router

    a = FastAPI()
    a.include_router(debug_router.router, prefix="/api")
    return a


def test_debug_disabled_404(monkeypatch):
    monkeypatch.setenv("KERNEL_DEBUG_ENABLED", "false")
    monkeypatch.setenv("API_SECRET", "x")
    from importlib import reload
    from backend.ai_kernel import debug_router

    reload(debug_router)
    a = FastAPI()
    a.include_router(debug_router.router, prefix="/api")
    with TestClient(a) as c:
        r = c.get("/api/kernel/debug/traces")
    assert r.status_code == 404


def test_debug_requires_bearer(app):
    with TestClient(app) as c:
        r = c.get("/api/kernel/debug/traces")
    assert r.status_code == 401


def test_debug_wrong_secret(app):
    with TestClient(app) as c:
        r = c.get(
            "/api/kernel/debug/traces",
            headers={"Authorization": "Bearer wrong"},
        )
    assert r.status_code == 401


def test_debug_ok_with_secret(app):
    with TestClient(app) as c:
        r = c.get(
            "/api/kernel/debug/traces",
            headers={"Authorization": "Bearer debug-secret-xyz"},
        )
    assert r.status_code == 200
    assert "traces" in r.json()


def test_no_secret_configured_404(monkeypatch):
    monkeypatch.setenv("KERNEL_DEBUG_ENABLED", "true")
    monkeypatch.delenv("API_SECRET", raising=False)
    monkeypatch.delenv("KERNEL_DEBUG_SECRET", raising=False)
    from importlib import reload
    from backend.ai_kernel import debug_router

    reload(debug_router)
    a = FastAPI()
    a.include_router(debug_router.router, prefix="/api")
    with TestClient(a) as c:
        r = c.get("/api/kernel/debug/traces")
    assert r.status_code == 404
