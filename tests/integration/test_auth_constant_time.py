"""API_SECRET auth 硬化：常數時間比對（hmac.compare_digest）+ 401 去敏。

只用假值（不含任何真實 secret）。驗證：
- 錯誤 token → 401，且回應內文/headers 不得回顯提交的 token 值。
- 正確 token → 不在 auth 層被 401。
- 缺 Authorization → 401，且 secret 不外流。
- 長度不同的 token → 401（compare_digest 行為與 == 一致，但為常數時間）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret-xyz-1234567890"
WRONG = "totally-wrong-token-0987654321"


def _main_with_secret(monkeypatch):
    monkeypatch.setenv("API_SECRET", SECRET)
    import main as main_mod

    main_mod.API_SECRET = SECRET
    return main_mod


@pytest.mark.integration
def test_wrong_token_is_401_and_value_not_echoed(monkeypatch):
    main_mod = _main_with_secret(monkeypatch)
    with TestClient(main_mod.app) as client:
        r = client.get("/api/tools", headers={"Authorization": f"Bearer {WRONG}"})
    assert r.status_code == 401
    # 去敏：提交的 token 值不得出現在內文或任一 header
    assert WRONG not in r.text
    for v in r.headers.values():
        assert WRONG not in v
    # 真正的 secret 更不得外流
    assert SECRET not in r.text


@pytest.mark.integration
def test_correct_token_passes_auth_gate(monkeypatch):
    main_mod = _main_with_secret(monkeypatch)
    with TestClient(main_mod.app) as client:
        r = client.get("/api/tools", headers={"Authorization": f"Bearer {SECRET}"})
    # 通過 auth 層（後續可能因 mock 環境有其他狀態碼，但不得是 401）
    assert r.status_code != 401
    assert r.headers.get("X-Request-ID")


@pytest.mark.integration
def test_missing_authorization_is_401_and_secret_not_leaked(monkeypatch):
    main_mod = _main_with_secret(monkeypatch)
    with TestClient(main_mod.app) as client:
        r = client.get("/api/tools")
    assert r.status_code == 401
    assert SECRET not in r.text


@pytest.mark.integration
def test_length_differing_token_is_401(monkeypatch):
    # compare_digest 對長度不同亦回 False（與 == 語義一致，差別在於常數時間）
    main_mod = _main_with_secret(monkeypatch)
    with TestClient(main_mod.app) as client:
        r = client.get(
            "/api/tools", headers={"Authorization": f"Bearer {SECRET}extra"}
        )
    assert r.status_code == 401
    assert (SECRET + "extra") not in r.text
