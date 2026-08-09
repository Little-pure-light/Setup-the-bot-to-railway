"""
記憶檢視「增量1：唯讀頁」— 後端直出（方向 C）。

契約與安全邊界：
- 後端 render 一個極簡、自足（不依賴任何 CDN／外部 script）的 HTML/JS 頁面於 `GET /memory-center`。
- 登入沿用 Supabase JWT：頁面以 email/password 直接呼叫 Supabase Auth REST
  (`{SUPABASE_URL}/auth/v1/token?grant_type=password`) 取得 access_token，
  再以 `Authorization: Bearer <token>` 呼叫既有 owner-scoped 唯讀 API `GET /api/memory-center`。
- 只注入「公開值」：SUPABASE_URL 與 SUPABASE_ANON_KEY（anon 為前端公開金鑰）。
  **絕不注入** service role key（SUPABASE_KEY）、API_SECRET 或任何伺服器祕密。
- 純唯讀：頁面無任何 mutation（無刪除／編輯／封存／匯出／寫入端點呼叫）。
- 未登入不顯示任何記憶資料；錯誤（401/403/5xx/network）顯示固定中文訊息，不回顯 raw detail。
- 記憶內容一律以 textContent 渲染（不使用 innerHTML），避免自身內容造成 XSS。
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

# 與 memory_router 的 allowlist 共用單一權威來源，避免漂移。
from backend.memory_router import MEMORY_TYPE_ALLOWLIST

router = APIRouter()


def _public_config() -> dict:
    """只回傳可公開注入頁面的設定；絕不含 service key / API_SECRET。"""
    return {
        "supabaseUrl": (os.getenv("SUPABASE_URL") or "").strip(),
        "supabaseAnonKey": (os.getenv("SUPABASE_ANON_KEY") or "").strip(),
        "memoryTypes": list(MEMORY_TYPE_ALLOWLIST),
    }


def _safe_json(value) -> str:
    """JSON 序列化並防止 `</script>` breakout（config 為受控環境值，仍做保底）。"""
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def render_memory_center_page() -> str:
    cfg = _safe_json(_public_config())
    return _PAGE_TEMPLATE.replace("__CONFIG_JSON__", cfg)


@router.get("/memory-center", response_class=HTMLResponse)
async def memory_center_page() -> HTMLResponse:
    """後端直出的唯讀記憶檢視頁（同源；呼叫 /api/memory-center）。"""
    return HTMLResponse(content=render_memory_center_page())


_PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex, nofollow" />
<title>小宸光 · 記憶檢視（唯讀）</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: system-ui, -apple-system, "Segoe UI", "PingFang TC",
    "Microsoft JhengHei", sans-serif; background: #f6f7fb; color: #1f2937;
    line-height: 1.5;
  }
  header { padding: 16px 20px; background: #fff; border-bottom: 1px solid #e5e7eb; }
  header h1 { margin: 0; font-size: 1.15rem; }
  header p { margin: 4px 0 0; font-size: 0.82rem; color: #6b7280; }
  main { max-width: 860px; margin: 0 auto; padding: 20px; }
  .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
  label { display: block; font-size: 0.82rem; color: #374151; margin-bottom: 4px; }
  input, select, button {
    font: inherit; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; color: inherit;
  }
  input, select { width: 100%; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; }
  .row > div { flex: 1 1 160px; min-width: 140px; }
  button { cursor: pointer; background: #4f46e5; color: #fff; border-color: #4f46e5; }
  button.secondary { background: #fff; color: #374151; border-color: #d1d5db; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .toolbar { display: flex; gap: 8px; align-items: flex-end; flex-wrap: wrap; }
  .msg { font-size: 0.85rem; padding: 10px 12px; border-radius: 8px; margin: 10px 0; }
  .msg.error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
  .msg.info { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
  .hidden { display: none !important; }
  ul.items { list-style: none; margin: 0; padding: 0; }
  li.item { border: 1px solid #eef2ff; border-radius: 10px; padding: 12px; margin-bottom: 10px; background: #fbfbff; }
  li.item .meta { font-size: 0.76rem; color: #6b7280; margin-bottom: 6px; display: flex; gap: 12px; flex-wrap: wrap; }
  li.item .u, li.item .a { white-space: pre-wrap; word-break: break-word; margin: 4px 0; }
  li.item .u { color: #111827; }
  li.item .a { color: #3730a3; }
  li.item .tag { display: inline-block; padding: 1px 8px; border-radius: 999px; background: #eef2ff; color: #4338ca; }
  .pager { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
  .pager span { font-size: 0.82rem; color: #6b7280; }
  .foot { font-size: 0.76rem; color: #9ca3af; text-align: center; margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>小宸光 · 記憶檢視</h1>
  <p>唯讀檢視「小宸光記得我什麼」。此頁不提供刪除或修改。</p>
</header>
<main>
  <!-- 登入區 -->
  <section id="loginCard" class="card">
    <h2 style="margin-top:0;font-size:1rem;">登入</h2>
    <div id="configError" class="msg error hidden">系統尚未設定登入服務，請稍後再試或聯絡管理者。</div>
    <div class="row">
      <div>
        <label for="email">Email</label>
        <input id="email" type="email" autocomplete="username" />
      </div>
      <div>
        <label for="password">密碼</label>
        <input id="password" type="password" autocomplete="current-password" />
      </div>
    </div>
    <div id="loginError" class="msg error hidden"></div>
    <div style="margin-top:12px;">
      <button id="loginBtn" type="button">登入</button>
    </div>
  </section>

  <!-- 檢視區 -->
  <section id="viewer" class="card hidden">
    <div class="toolbar">
      <div style="flex:2 1 200px;">
        <label for="q">搜尋（本人記憶內容）</label>
        <input id="q" type="search" maxlength="100" placeholder="輸入關鍵字…" />
      </div>
      <div style="flex:1 1 160px;">
        <label for="type">類型</label>
        <select id="type"></select>
      </div>
      <div style="flex:1 1 150px;">
        <label for="from">起始日期</label>
        <input id="from" type="date" />
      </div>
      <div style="flex:1 1 150px;">
        <label for="to">結束日期</label>
        <input id="to" type="date" />
      </div>
      <div style="flex:0 0 auto;display:flex;gap:8px;">
        <button id="applyBtn" type="button">套用</button>
        <button id="resetBtn" type="button" class="secondary">清除</button>
        <button id="logoutBtn" type="button" class="secondary">登出</button>
      </div>
    </div>
    <div id="filterError" class="msg error hidden"></div>
    <div id="scopeNotice" class="msg info hidden">搜尋範圍為最近 200 筆本人記憶的比對結果。</div>

    <div id="listError" class="msg error hidden"></div>
    <div id="empty" class="msg info hidden">目前沒有可顯示的記憶。</div>
    <ul id="items" class="items"></ul>

    <div class="pager">
      <button id="prevBtn" type="button" class="secondary">上一頁</button>
      <span id="pageInfo">第 1 頁</span>
      <button id="nextBtn" type="button" class="secondary">下一頁</button>
    </div>
    <div class="foot">唯讀頁 · 僅顯示登入者本人記憶 · 不含內部欄位</div>
  </section>
</main>

<script>
"use strict";
(function () {
  var CONFIG = __CONFIG_JSON__;
  var TOKEN_KEY = "xcg_mc_token";
  var PAGE_LIMIT = 20;

  var state = {
    offset: 0,
    applied: { q: "", memory_type: "", created_from: "", created_to: "" },
  };

  function $(id) { return document.getElementById(id); }
  function show(el) { el.classList.remove("hidden"); }
  function hide(el) { el.classList.add("hidden"); }
  function setError(el, text) { el.textContent = text; show(el); }
  function clearError(el) { el.textContent = ""; hide(el); }

  function getToken() { try { return sessionStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { sessionStorage.setItem(TOKEN_KEY, t); } catch (e) {} }
  function clearToken() { try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) {} }

  function configReady() {
    return !!(CONFIG && CONFIG.supabaseUrl && CONFIG.supabaseAnonKey);
  }

  // ---- 類型下拉 ----
  function fillTypes() {
    var sel = $("type");
    var opt0 = document.createElement("option");
    opt0.value = ""; opt0.textContent = "全部類型";
    sel.appendChild(opt0);
    var types = (CONFIG && CONFIG.memoryTypes) || [];
    for (var i = 0; i < types.length; i++) {
      var o = document.createElement("option");
      o.value = types[i]; o.textContent = types[i];
      sel.appendChild(o);
    }
  }

  // ---- 登入（Supabase Auth REST；不依賴外部 SDK）----
  function login() {
    clearError($("loginError"));
    if (!configReady()) { show($("configError")); return; }
    var email = $("email").value.trim();
    var password = $("password").value;
    if (!email || !password) { setError($("loginError"), "請輸入 Email 與密碼。"); return; }
    $("loginBtn").disabled = true;
    var url = CONFIG.supabaseUrl.replace(/\/+$/, "") + "/auth/v1/token?grant_type=password";
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "apikey": CONFIG.supabaseAnonKey },
      body: JSON.stringify({ email: email, password: password }),
    }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (r) {
      if (r.ok && r.data && r.data.access_token) {
        setToken(r.data.access_token);
        $("password").value = "";
        enterViewer();
      } else {
        setError($("loginError"), "登入失敗，請確認 Email 與密碼是否正確。");
      }
    }).catch(function () {
      setError($("loginError"), "無法連線登入服務，請稍後再試。");
    }).then(function () {
      $("loginBtn").disabled = false;
    });
  }

  function logout() {
    clearToken();
    hide($("viewer"));
    show($("loginCard"));
  }

  function enterViewer() {
    hide($("loginCard"));
    show($("viewer"));
    state.offset = 0;
    state.applied = { q: "", memory_type: "", created_from: "", created_to: "" };
    loadPage();
  }

  // ---- 篩選驗證 ----
  function applyFilters() {
    clearError($("filterError"));
    var q = $("q").value.trim();
    var type = $("type").value;
    var from = $("from").value;
    var to = $("to").value;
    if (q.length > 100) { setError($("filterError"), "搜尋字數過長，請縮短至 100 字以內。"); return; }
    if (from && to && from > to) { setError($("filterError"), "起始日期不可晚於結束日期。"); return; }
    state.applied = { q: q, memory_type: type, created_from: from, created_to: to };
    state.offset = 0;
    loadPage();
  }

  function resetFilters() {
    $("q").value = ""; $("type").value = ""; $("from").value = ""; $("to").value = "";
    clearError($("filterError"));
    state.applied = { q: "", memory_type: "", created_from: "", created_to: "" };
    state.offset = 0;
    loadPage();
  }

  // ---- 只挑安全欄位進 view model；即使回應夾帶 owner/ai_id/embedding/email/token/metadata 也不渲染 ----
  function toSafe(raw) {
    return {
      id: raw && raw.id,
      type: raw && raw.memory_type ? String(raw.memory_type) : "",
      createdAt: raw && raw.created_at ? String(raw.created_at).slice(0, 19).replace("T", " ") : "",
      userText: raw && raw.user_message ? String(raw.user_message) : "",
      assistantText: raw && raw.assistant_message ? String(raw.assistant_message) : "",
      importance: raw && raw.importance_score != null ? raw.importance_score : null,
      access: raw && raw.access_count != null ? raw.access_count : null,
    };
  }

  function renderItems(list) {
    var ul = $("items");
    ul.textContent = "";
    for (var i = 0; i < list.length; i++) {
      var it = toSafe(list[i]);
      var li = document.createElement("li");
      li.className = "item";

      var meta = document.createElement("div");
      meta.className = "meta";
      if (it.type) {
        var tag = document.createElement("span");
        tag.className = "tag"; tag.textContent = it.type;
        meta.appendChild(tag);
      }
      if (it.createdAt) {
        var t = document.createElement("span"); t.textContent = it.createdAt; meta.appendChild(t);
      }
      if (it.importance != null) {
        var imp = document.createElement("span"); imp.textContent = "重要性 " + it.importance; meta.appendChild(imp);
      }
      if (it.access != null) {
        var ac = document.createElement("span"); ac.textContent = "取用 " + it.access; meta.appendChild(ac);
      }
      li.appendChild(meta);

      if (it.userText) {
        var u = document.createElement("div"); u.className = "u"; u.textContent = "我：" + it.userText; li.appendChild(u);
      }
      if (it.assistantText) {
        var a = document.createElement("div"); a.className = "a"; a.textContent = "小宸光：" + it.assistantText; li.appendChild(a);
      }
      ul.appendChild(li);
    }
  }

  function buildQuery() {
    var a = state.applied;
    var params = [];
    params.push("limit=" + PAGE_LIMIT);
    params.push("offset=" + state.offset);
    if (a.q) params.push("q=" + encodeURIComponent(a.q));
    if (a.memory_type) params.push("memory_type=" + encodeURIComponent(a.memory_type));
    if (a.created_from) params.push("created_from=" + encodeURIComponent(a.created_from));
    if (a.created_to) params.push("created_to=" + encodeURIComponent(a.created_to));
    return params.join("&");
  }

  function loadPage() {
    clearError($("listError"));
    hide($("empty"));
    hide($("scopeNotice"));
    var token = getToken();
    if (!token) { logout(); return; }

    $("applyBtn").disabled = true; $("prevBtn").disabled = true; $("nextBtn").disabled = true;

    fetch("/api/memory-center?" + buildQuery(), {
      method: "GET",
      headers: { "Authorization": "Bearer " + token },
    }).then(function (res) {
      if (res.status === 401) { clearToken(); throw { fixed: "登入已過期，請重新登入。", relogin: true }; }
      if (res.status === 403) { throw { fixed: "沒有權限檢視這筆資料。" }; }
      if (res.status === 422) { throw { fixed: "篩選條件不正確，請調整後再試。" }; }
      if (!res.ok) { throw { fixed: "服務暫時無法使用，請稍後再試。" }; }
      return res.json();
    }).then(function (data) {
      var items = (data && data.items) || [];
      renderItems(items);
      if (!items.length) { show($("empty")); }
      if (data && data.search_scope) { show($("scopeNotice")); }
      $("pageInfo").textContent = "第 " + (Math.floor(state.offset / PAGE_LIMIT) + 1) + " 頁";
      $("prevBtn").disabled = state.offset <= 0;
      // 少於整頁代表沒有下一頁
      $("nextBtn").disabled = items.length < PAGE_LIMIT;
    }).catch(function (err) {
      renderItems([]);
      var text = (err && err.fixed) || "無法連線伺服器，請檢查網路後再試。";
      setError($("listError"), text);
      if (err && err.relogin) { logout(); }
    }).then(function () {
      $("applyBtn").disabled = false;
    });
  }

  function prevPage() {
    if (state.offset <= 0) return;
    state.offset = Math.max(0, state.offset - PAGE_LIMIT);
    loadPage();
  }
  function nextPage() {
    state.offset += PAGE_LIMIT;
    loadPage();
  }

  // ---- 綁定 ----
  document.addEventListener("DOMContentLoaded", function () {
    if (!configReady()) { show($("configError")); }
    fillTypes();
    $("loginBtn").addEventListener("click", login);
    $("password").addEventListener("keydown", function (e) { if (e.key === "Enter") login(); });
    $("applyBtn").addEventListener("click", applyFilters);
    $("resetBtn").addEventListener("click", resetFilters);
    $("logoutBtn").addEventListener("click", logout);
    $("prevBtn").addEventListener("click", prevPage);
    $("nextBtn").addEventListener("click", nextPage);
    $("q").addEventListener("keydown", function (e) { if (e.key === "Enter") applyFilters(); });
    // 已有 session token → 直接進檢視
    if (getToken()) { enterViewer(); }
  });
})();
</script>
</body>
</html>
"""
