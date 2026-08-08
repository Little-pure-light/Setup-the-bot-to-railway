"""Deterministic unit tests for the Gate 1 persistence indicator.

驗證：data_root 解析、mount 偵測 → mode(volume/ephemeral/unknown)、可寫檢查、
啟動 ensure_persistence_root、以及 /ready readiness_payload 的去敏 persistence 欄位。
不依賴真實掛卷（以 monkeypatch 模擬 mount / 不可寫），跨平台可跑。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.modules import persistence as P


def _clear_root_env(monkeypatch):
    monkeypatch.delenv("PERSISTENCE_DATA_ROOT", raising=False)


def test_data_root_env_override(monkeypatch, tmp_path):
    target = tmp_path / "custom_data"
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(target))
    assert P.data_root() == target


def test_data_root_default_is_repo_data(monkeypatch):
    _clear_root_env(monkeypatch)
    # 預設 = <repo_root>/data，以程式碼位置錨定（parents[2]），與 CWD 無關。
    expected = Path(P.__file__).resolve().parents[2] / "data"
    assert P.data_root() == expected
    assert P.data_root().name == "data"


def test_status_existing_dir_is_ephemeral(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(tmp_path))
    st = P.persistence_status(probe_write=True)
    assert st["exists"] is True
    assert st["writable"] is True
    # 一般 tmp 目錄與其父同一裝置 → 非 mount → ephemeral
    assert st["is_mount"] is False
    assert st["mode"] == "ephemeral"
    assert st["root"] == str(tmp_path)


def test_status_missing_dir_is_unknown(monkeypatch, tmp_path):
    missing = tmp_path / "does_not_exist"
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(missing))
    st = P.persistence_status(probe_write=False)
    assert st["exists"] is False
    assert st["mode"] == "unknown"


def test_status_volume_when_separate_mount(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(tmp_path))
    # 模擬 data/ 掛在獨立卷（st_dev 與父不同）
    monkeypatch.setattr(P, "_is_separate_mount", lambda _p: True)
    st = P.persistence_status(probe_write=False)
    assert st["is_mount"] is True
    assert st["mode"] == "volume"


def test_status_not_writable(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(P.os, "access", lambda *a, **k: False)
    st = P.persistence_status(probe_write=False)
    assert st["writable"] is False
    # 存在但非 mount → 仍為 ephemeral（可寫與否不改變 mode）
    assert st["mode"] == "ephemeral"


def test_write_probe_is_removed(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(tmp_path))
    st = P.persistence_status(probe_write=True)
    assert st["writable"] is True
    # 探測檔必須刪除，不殘留
    assert not (tmp_path / P._WRITE_PROBE_NAME).exists()


def test_ensure_persistence_root_creates_and_probes(monkeypatch, tmp_path):
    target = tmp_path / "data_root_new"
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(target))
    assert not target.exists()
    st = P.ensure_persistence_root()
    assert target.exists()
    assert st["exists"] is True
    assert st["writable"] is True
    assert st["mode"] in ("ephemeral", "volume")
    assert not (target / P._WRITE_PROBE_NAME).exists()


def test_status_is_desensitized(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(tmp_path))
    st = P.persistence_status(probe_write=True)
    # 只含固定鍵；值為固定字串/布林/路徑，無 secret 欄位
    assert set(st.keys()) == {"mode", "root", "exists", "writable", "is_mount"}
    assert st["mode"] in ("volume", "ephemeral", "unknown")


def test_readiness_payload_exposes_persistence(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(tmp_path))
    # 讓關鍵設定齊全，避免 not_ready 干擾（persistence 為資訊性，不改 status）
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://mock.supabase.local")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    from backend import health

    body = health.readiness_payload(check_dns=False)
    assert body["services"]["persistence"] in ("volume", "ephemeral", "unknown")
    assert isinstance(body.get("persistence"), dict)
    assert body["persistence"].get("mode") == body["services"]["persistence"]
    assert "persistence" in body["notes"]


def test_persistence_does_not_flip_status(monkeypatch, tmp_path):
    # ephemeral persistence 不得把一個原本 ok/degraded 的 readiness 變成 not_ready
    monkeypatch.setenv("PERSISTENCE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://mock.supabase.local")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    from backend import health

    body = health.readiness_payload(check_dns=False)
    assert body["services"]["persistence"] == "ephemeral"
    # persistence 為資訊性，status 由既有 openai/supabase/redis 規則決定，不因 ephemeral 變 not_ready
    assert body["status"] != "not_ready"
