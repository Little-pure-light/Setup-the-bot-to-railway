"""
Task008-001 — 私有 owner-scoped 封存端點 deterministic 測試。

走真實 FastAPI endpoint／dependency 邊界（TestClient）。
重度 Mock，不連正式 Supabase／Redis／IPFS，不寫入正式資料庫。
"""
from __future__ import annotations

import importlib
import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


OWNER_A = "owner-A-uuid"
CONV_ID = "conv-secret-should-not-be-logged"
JWT_A = "jwt-A-should-not-be-logged"


class _FakeQuery:
    """記錄 eq 過濾條件，回傳（或拋出）設定好的資料。"""

    def __init__(self, state):
        self.state = state

    def select(self, cols):
        self.state["select"] = cols
        return self

    def eq(self, key, value):
        self.state.setdefault("eq", {})[key] = value
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        if self.state.get("raise"):
            raise RuntimeError("supabase boom internal detail")
        return SimpleNamespace(data=list(self.state.get("data", [])))


class _FakeTable:
    def __init__(self, state):
        self.state = state
        # insert 必須完全不被呼叫（case 8）
        self.insert = MagicMock(side_effect=AssertionError("insert must not be called"))

    def select(self, cols):
        return _FakeQuery(self.state).select(cols)


class _FakeSupabase:
    def __init__(self, state):
        self.state = state

    def table(self, name):
        self.state.setdefault("tables", []).append(name)
        return _FakeTable(self.state)


@pytest.fixture
def arch_env(monkeypatch):
    """回傳 (client, state, module)；state 用來設定/檢查 Mock 行為。"""
    import backend.archive_conversation as arch

    state = {"data": []}

    def fake_get_supabase():
        state["get_supabase_called"] = state.get("get_supabase_called", 0) + 1
        return _FakeSupabase(state)

    monkeypatch.setattr(arch, "get_supabase", fake_get_supabase)
    # 預設：任何非空 token 視為有效 owner_A；由個別測試覆寫
    monkeypatch.setattr(
        arch, "get_user_from_token", lambda tok: SimpleNamespace(id=OWNER_A) if tok else None
    )
    monkeypatch.setenv("AI_ID", "xiaochenguang_v1")

    app = FastAPI()
    app.include_router(arch.router, prefix="/api")
    with TestClient(app) as client:
        yield client, state, arch


def _auth(tok=JWT_A):
    return {"Authorization": f"Bearer {tok}"}


# ── case 1：正常 owner + 自己的 conversation → success/private/CID null ──────────
def test_owner_success_private_no_cid(arch_env):
    client, state, _ = arch_env
    state["data"] = [{"id": 1, "created_at": "t1"}, {"id": 2, "created_at": "t2"}]
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["mode"] == "private_existing_memory"
    assert body["message_count"] == 2
    assert body["attachments_archived"] is False
    assert body["ipfs_cid"] is None and body["gateway_url"] is None and body["archive_id"] is None
    # owner-scoped 過濾條件齊全
    eq = state["eq"]
    assert eq["conversation_id"] == CONV_ID
    assert eq["user_id"] == OWNER_A
    assert eq["ai_id"] == "xiaochenguang_v1"
    assert eq["memory_type"] == "conversation"


# ── case 2：缺／格式錯／無效 JWT → 401 ─────────────────────────────────────────
def test_missing_authorization_401(arch_env):
    client, state, _ = arch_env
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID})
    assert r.status_code == 401
    assert "tables" not in state  # 未進行任何 DB 讀取


def test_malformed_authorization_401(arch_env):
    client, _, _ = arch_env
    r = client.post(
        "/api/archive_conversation",
        json={"conversation_id": CONV_ID},
        headers={"Authorization": "Token abc"},
    )
    assert r.status_code == 401


def test_invalid_jwt_401(arch_env, monkeypatch):
    client, state, arch = arch_env
    monkeypatch.setattr(arch, "get_user_from_token", lambda tok: None)
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    assert r.status_code == 401
    assert "tables" not in state


# ── case 3：body user_id 與 principal 不符 → 403，且零 DB／IPFS 副作用 ───────────
def test_body_user_id_mismatch_403_no_side_effects(arch_env):
    client, state, _ = arch_env
    r = client.post(
        "/api/archive_conversation",
        json={"conversation_id": CONV_ID, "user_id": "someone-else"},
        headers=_auth(),
    )
    assert r.status_code == 403
    assert "tables" not in state
    assert state.get("get_supabase_called") is None


def test_body_user_id_equal_principal_ok(arch_env):
    client, state, _ = arch_env
    state["data"] = [{"id": 1, "created_at": "t1"}]
    r = client.post(
        "/api/archive_conversation",
        json={"conversation_id": CONV_ID, "user_id": OWNER_A},
        headers=_auth(),
    )
    assert r.status_code == 200


# ── case 4：Owner A 取 Owner B 的 conversation → 一致 404，不洩漏存在性 ──────────
def test_cross_owner_returns_consistent_404(arch_env):
    client, state, _ = arch_env
    # A 的 owner 過濾會查不到 B 的列 → data 空
    state["data"] = []
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    assert r.status_code == 404
    # 與「對話不存在」同一種 404、同一訊息，無法區分是否存在
    assert state["eq"]["user_id"] == OWNER_A


# ── case 5：同 conversation id 混入另一 owner／AI／typed → 只採正確 owner+AI conversation ─
def test_scoped_filters_exclude_other_owner_ai_and_typed(arch_env):
    client, state, _ = arch_env
    # 模擬 DB 已依過濾條件只回正確 2 列 conversation
    state["data"] = [{"id": 10, "created_at": "t1"}, {"id": 11, "created_at": "t2"}]
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    assert r.status_code == 200
    eq = state["eq"]
    # 四個過濾條件缺一不可
    assert set(["conversation_id", "user_id", "ai_id", "memory_type"]).issubset(eq.keys())
    assert eq["memory_type"] == "conversation"  # typed memory 不會被納入
    assert r.json()["message_count"] == 2


# ── case 6：empty conversation → 404 ───────────────────────────────────────────
def test_empty_conversation_404(arch_env):
    client, state, _ = arch_env
    state["data"] = []
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    assert r.status_code == 404


# ── case 7：Supabase error/timeout → 去敏 5xx，不回假 success、不曝露內部錯誤 ─────
def test_supabase_error_sanitized_5xx(arch_env):
    client, state, _ = arch_env
    state["raise"] = True
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    assert 500 <= r.status_code < 600
    body = r.json()
    assert body.get("success") is not True
    assert "boom" not in str(body) and "internal detail" not in str(body)


# ── case 8：IPFS handler／Redis 附件讀取／archive table insert 呼叫次數全部 = 0 ──
def test_no_ipfs_redis_or_archive_insert_dependencies(arch_env):
    client, state, arch = arch_env
    state["data"] = [{"id": 1, "created_at": "t1"}]
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    assert r.status_code == 200
    # 只讀 memories 表，從不碰 archive table
    assert state.get("tables") == [arch._memories_table()]
    # 模組已完全移除 IPFS／Redis 執行依賴
    assert not hasattr(arch, "ipfs_handler")
    assert not hasattr(arch, "redis_interface")
    src = inspect.getsource(arch)
    for banned in ("upload_to_ipfs", "get_ipfs_handler", "get_uploaded_files"):
        assert banned not in src, f"archive 模組不應再引用 {banned}"


# ── case 9：response 舊 optional CID／gateway 欄位向後相容且為 null ───────────────
def test_response_backward_compatible_null_fields(arch_env):
    client, state, _ = arch_env
    state["data"] = [{"id": 1, "created_at": "t1"}]
    r = client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
    body = r.json()
    for k in ("ipfs_cid", "gateway_url", "archive_id"):
        assert k in body and body[k] is None
    assert "archived_at" in body and body["archived_at"]


# ── case 10：日誌不含 JWT／全文／CID／真實 user／conversation id ──────────────────
def test_logs_are_desensitized(arch_env, caplog):
    client, state, _ = arch_env
    state["data"] = [{"id": 1, "created_at": "t1"}]
    with caplog.at_level("INFO"):
        client.post("/api/archive_conversation", json={"conversation_id": CONV_ID}, headers=_auth())
        # 另跑一次未授權路徑
        client.post("/api/archive_conversation", json={"conversation_id": CONV_ID})
    blob = "\n".join(rec.getMessage() for rec in caplog.records)
    assert JWT_A not in blob
    assert CONV_ID not in blob
    assert OWNER_A not in blob
