"""
記憶檢視「增量1：唯讀頁」— deterministic 整合測試（走真實 FastAPI endpoint / dependency）。

覆蓋：
- 後端直出頁面：GET /memory-center 回 200 HTML、注入公開 config、不外洩伺服器祕密、無 mutation 控制。
- owner-scoped 唯讀 API：GET /api/memory-center
  * 未登入（缺／格式錯／無效 JWT、API_SECRET-only）→ 401，且不回任何記憶資料。
  * 只回安全欄位（即便 DB 夾帶 owner/ai_id/embedding/email/token 也不外洩）。
  * 查詢一律綁定 JWT principal user_id + 目前 ai_id（不信任前端傳入身分）。
  * 分頁 / 篩選契約：limit/offset echo、memory_type allowlist、日期 grammar、搜尋範圍揭露。
  * 錯誤去敏：DB 例外 → 502 固定中文訊息，不回顯 raw detail。

重度 Mock，不連正式 Supabase，不寫入任何資料庫。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


OWNER_A = "owner-A-uuid"
OWNER_B = "owner-B-uuid"
JWT_A = "jwt-A-should-not-be-logged"
AI_ID = "xiaochenguang_v1"
MARKER = "SECRET_INTERNAL_should_not_leak_9f2b"


class _FakeQuery:
    def __init__(self, state):
        self.state = state

    def select(self, cols):
        self.state["select"] = cols
        return self

    def eq(self, key, value):
        self.state.setdefault("eq", {})[key] = value
        self.state.setdefault("filters", []).append(("eq", key, value))
        return self

    def gte(self, key, value):
        self.state.setdefault("filters", []).append(("gte", key, value))
        return self

    def lte(self, key, value):
        self.state.setdefault("filters", []).append(("lte", key, value))
        return self

    def order(self, col, desc=False):
        self.state.setdefault("order", []).append((col, bool(desc)))
        return self

    def range(self, start, end):
        self.state["range"] = (start, end)
        return self

    def limit(self, n):
        self.state["limit"] = n
        return self

    def execute(self):
        if self.state.get("raise"):
            raise RuntimeError(f"supabase boom internal detail {OWNER_B} {MARKER}")
        return SimpleNamespace(data=list(self.state.get("data", [])))


class _FakeTable:
    def __init__(self, state):
        self.state = state

    def select(self, cols):
        return _FakeQuery(self.state).select(cols)


class _FakeSupabase:
    def __init__(self, state):
        self.state = state

    def table(self, name):
        self.state.setdefault("tables", []).append(name)
        return _FakeTable(self.state)


@pytest.fixture
def client(monkeypatch):
    import backend.memory_router as mem
    import backend.auth_principal as principal

    state = {"data": []}
    monkeypatch.setattr(mem, "supabase", _FakeSupabase(state))
    # 只有 JWT_A 換到 OWNER_A；其餘（含 API_SECRET-only / 無效 / 過期）→ None → 401
    monkeypatch.setattr(
        principal,
        "get_user_from_token",
        lambda tok: SimpleNamespace(id=OWNER_A) if tok == JWT_A else None,
    )
    monkeypatch.setenv("AI_ID", AI_ID)

    app = FastAPI()
    app.include_router(mem.router, prefix="/api")
    with TestClient(app) as c:
        yield c, state, mem


def _auth(tok=JWT_A):
    return {"Authorization": f"Bearer {tok}"}


# --------------------------------------------------------------------------
# owner-scoped 唯讀 API：授權
# --------------------------------------------------------------------------

def test_missing_auth_returns_401_and_no_data(client):
    c, state, _ = client
    r = c.get("/api/memory-center")
    assert r.status_code == 401
    body = r.json()
    assert "items" not in body  # 未登入不得回任何記憶結構


def test_malformed_bearer_returns_401(client):
    c, _, _ = client
    r = c.get("/api/memory-center", headers={"Authorization": "Token abc"})
    assert r.status_code == 401


def test_api_secret_only_is_not_a_principal_401(client):
    c, _, _ = client
    # 非 Supabase JWT（例如 API_SECRET-only 值）→ get_user_from_token 回 None → 401
    r = c.get("/api/memory-center", headers=_auth("api-secret-only-not-a-jwt"))
    assert r.status_code == 401


def test_authorized_binds_principal_and_ai_id(client):
    c, state, _ = client
    state["data"] = []
    r = c.get("/api/memory-center", headers=_auth())
    assert r.status_code == 200
    eqs = state.get("eq", {})
    # 一律以 JWT principal + 目前 ai_id 綁定；不信任前端身分
    assert eqs.get("user_id") == OWNER_A
    assert eqs.get("ai_id") == AI_ID


# --------------------------------------------------------------------------
# 安全欄位 allowlist
# --------------------------------------------------------------------------

def test_only_safe_fields_returned(client):
    c, state, _ = client
    state["data"] = [
        {
            "id": 1,
            "memory_type": "conversation",
            "created_at": "2026-08-01T10:00:00+00:00",
            "conversation_id": "conv-1",
            "user_message": "我今天很累",
            "assistant_message": "辛苦了，休息一下。",
            "importance_score": 0.7,
            "access_count": 2,
            # 以下敏感/內部欄位即使 DB 夾帶也不得外洩
            "user_id": OWNER_A,
            "ai_id": AI_ID,
            "embedding": [0.1, 0.2, 0.3],
            "email": "secret@example.com",
            "token": MARKER,
            "metadata": {"internal": MARKER},
        }
    ]
    r = c.get("/api/memory-center", headers=_auth())
    assert r.status_code == 200
    item = r.json()["items"][0]
    allowed = {
        "id", "memory_type", "created_at", "conversation_id",
        "user_message", "assistant_message", "importance_score", "access_count",
    }
    assert set(item.keys()) <= allowed
    for forbidden in ("user_id", "ai_id", "embedding", "email", "token", "metadata"):
        assert forbidden not in item
    # 也確認 select 欄位清單本身不含 embedding / owner / ai
    sel = state.get("select", "")
    for forbidden in ("embedding", "user_id", "ai_id", "email", "token"):
        assert forbidden not in sel


# --------------------------------------------------------------------------
# 分頁 / 篩選契約
# --------------------------------------------------------------------------

def test_pagination_echo_and_range(client):
    c, state, _ = client
    state["data"] = []
    r = c.get("/api/memory-center?limit=10&offset=20", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 10
    assert body["offset"] == 20
    assert state.get("range") == (20, 29)


def test_limit_upper_bound_rejected(client):
    c, _, _ = client
    r = c.get("/api/memory-center?limit=999", headers=_auth())
    assert r.status_code == 422


def test_unknown_memory_type_rejected(client):
    c, _, _ = client
    r = c.get("/api/memory-center?memory_type=definitely_not_a_type", headers=_auth())
    assert r.status_code == 422


def test_known_memory_type_accepted_and_scoped(client):
    c, state, _ = client
    state["data"] = []
    r = c.get("/api/memory-center?memory_type=conversation", headers=_auth())
    assert r.status_code == 200
    assert state.get("eq", {}).get("memory_type") == "conversation"


def test_bad_date_grammar_rejected(client):
    c, _, _ = client
    r = c.get("/api/memory-center?created_from=2026/08/01", headers=_auth())
    assert r.status_code == 422


def test_from_after_to_rejected(client):
    c, _, _ = client
    r = c.get(
        "/api/memory-center?created_from=2026-08-10&created_to=2026-08-01",
        headers=_auth(),
    )
    assert r.status_code == 422


def test_search_scope_disclosed_and_owner_scoped(client):
    c, state, _ = client
    state["data"] = [
        {
            "id": 2, "memory_type": "conversation", "created_at": "2026-08-02T00:00:00+00:00",
            "conversation_id": "c2", "user_message": "喜歡看海", "assistant_message": "海很療癒",
            "importance_score": 0.5, "access_count": 1,
        },
        {
            "id": 3, "memory_type": "conversation", "created_at": "2026-08-01T00:00:00+00:00",
            "conversation_id": "c3", "user_message": "今天吃拉麵", "assistant_message": "好吃嗎",
            "importance_score": 0.4, "access_count": 1,
        },
    ]
    r = c.get("/api/memory-center?q=海", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    # 搜尋範圍誠實揭露
    assert body["search_scope"] == "recent_200_owner_rows"
    # deterministic in-Python 子字串過濾：只留含「海」者
    assert [it["id"] for it in body["items"]] == [2]
    # 搜尋仍先 owner + ai 綁定
    assert state.get("eq", {}).get("user_id") == OWNER_A
    assert state.get("eq", {}).get("ai_id") == AI_ID


# --------------------------------------------------------------------------
# 錯誤去敏
# --------------------------------------------------------------------------

def test_db_error_desensitized_502(client):
    c, state, _ = client
    state["raise"] = True
    r = c.get("/api/memory-center", headers=_auth())
    assert r.status_code == 502
    detail = r.json().get("detail", "")
    assert MARKER not in detail
    assert OWNER_B not in detail
    assert detail == "記憶服務暫時無法使用，請稍後再試"


# --------------------------------------------------------------------------
# 後端直出頁面（方向 C）
# --------------------------------------------------------------------------

@pytest.fixture
def page_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://mock.supabase.local")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "public-anon-key-safe")
    # 伺服器祕密：頁面絕不可注入
    monkeypatch.setenv("SUPABASE_KEY", "SERVICE_ROLE_SECRET_must_not_leak")
    monkeypatch.setenv("API_SECRET", "API_SECRET_must_not_leak")

    import importlib
    import backend.memory_center_page as page
    importlib.reload(page)

    app = FastAPI()
    app.include_router(page.router)
    with TestClient(app) as c:
        yield c


def test_page_served_html_200(page_client):
    r = page_client.get("/memory-center")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "記憶檢視" in r.text


def test_page_injects_public_config_only(page_client):
    r = page_client.get("/memory-center")
    html = r.text
    # 公開值可注入
    assert "https://mock.supabase.local" in html
    assert "public-anon-key-safe" in html
    # 伺服器祕密不得出現在頁面
    assert "SERVICE_ROLE_SECRET_must_not_leak" not in html
    assert "API_SECRET_must_not_leak" not in html


def test_page_has_no_mutation_controls(page_client):
    html = page_client.get("/memory-center").text
    # 唯讀增量：頁面不得對後端發出任何 mutation HTTP 方法。
    for banned_method in ("DELETE", "PUT", "PATCH"):
        assert f'"{banned_method}"' not in html
        assert f"'{banned_method}'" not in html
    # 對本專案 API（/api/…）的唯一呼叫必須是唯讀：出現的 /api/ 端點只有 memory-center。
    # （login 的 POST 是打 Supabase Auth REST，不是本專案 mutation 端點。）
    assert "/api/memory-center" in html
    lowered = html.lower()
    for banned_api in ("/api/memory/delete", "/api/memories/delete", "delete_memory"):
        assert banned_api not in lowered
    # 不得有刪除/編輯/封存的互動按鈕文案（描述性「不提供刪除或修改」不算控制項，故用按鈕字樣判斷）。
    for banned_button in (">刪除<", ">編輯<", ">封存<", ">匯出<"):
        assert banned_button not in html
