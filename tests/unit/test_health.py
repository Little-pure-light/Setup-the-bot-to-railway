"""P1-10: Liveness / Readiness（設定層級，非完整 DB）"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_liveness_payload_no_secrets():
    from backend.health import liveness_payload

    p = liveness_payload()
    assert p["status"] == "ok"
    assert p["check"] == "liveness"
    assert "version" in p
    blob = str(p)
    assert "sk-" not in blob
    assert "eyJ" not in blob


@pytest.mark.unit
def test_readiness_config_only_no_dns_by_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.setenv("READY_CHECK_SUPABASE_DNS", "false")
    from backend.health import readiness_payload

    p = readiness_payload()
    assert p["services"]["openai_config"] == "configured"
    assert p["services"]["supabase"] == "config_only"
    assert p["services"]["redis"] == "unavailable"
    assert p["notes"]["supabase"] == "config_and_optional_dns_only_not_db_probe"
    assert p["status"] in ("ok", "degraded")
    assert "OPENAI_API_KEY" not in str(p)


@pytest.mark.unit
def test_readiness_not_ready_missing_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "http://mock.supabase.local")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test")
    from backend.health import readiness_payload

    p = readiness_payload()
    assert p["status"] == "not_ready"
    assert p["services"]["openai_config"] == "missing"


@pytest.mark.unit
def test_git_commit_optional_and_sanitized(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123def456")
    from backend.health import liveness_payload

    p = liveness_payload()
    assert p.get("git_commit") == "abc123def456"


@pytest.mark.unit
def test_git_commit_strips_non_alnum(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "deadbeef;rm")
    from backend.health import liveness_payload

    p = liveness_payload()
    assert p.get("git_commit") == "deadbeefrm"


@pytest.mark.integration
def test_live_ready_endpoints():
    from main import app

    with TestClient(app) as client:
        r = client.get("/live")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.headers.get("X-Request-ID")

        r2 = client.get("/api/ready")
        assert r2.status_code in (200, 503)
        body = r2.json()
        assert "services" in body
        assert "notes" in body
        assert "sk-proj" not in r2.text
