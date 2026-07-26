# 環境變數一覽（真實程式引用）

**警告：正式值不得寫入 Git / 測試 / Issue。**

## 後端必要

| 變數 | 用途 | 預設 |
|------|------|------|
| `OPENAI_API_KEY` | GPT / embedding / moderation | 無 |
| `SUPABASE_URL` | Supabase 專案 URL | 無 |
| `SUPABASE_ANON_KEY` 或 `SUPABASE_KEY` | Supabase 金鑰 | 無 |

## 後端常用可選

| 變數 | 用途 | 預設 |
|------|------|------|
| `PORT` | 監聽埠 | `5000`（main）/ Railway 注入 |
| `API_SECRET` | 保護 `/api/*` 與 `/v1/*`（Open WebUI OpenAI 相容 API） | 空=不啟用 |
| `AI_ID` | 預設 AI 實例 | `xiaochenguang_v1` |
| `SUPABASE_MEMORIES_TABLE` | 記憶表名 | `xiaochenguang_memories` |
| `OPENAI_ORG_ID` / `OPENAI_PROJECT_ID` | OpenAI 組織 | 空 |
| `REDIS_URL` | Redis 連線（Railway 私有網路優先；`redis://` **不會**再被強制改成 `rediss://`） | 無 → mock |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_TOKEN` / `REDIS_ENDPOINT` | 替代連線方式 | 見 `redis_interface.py` |
| `REDIS_SSL` | 強制 TLS true/false | 空＝依 URL scheme；host+token 預設 true |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | 連線逾時 | `2.0` |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | 讀寫逾時 | `2.0` |
| `MEMORY_REDIS_TTL_SECONDS` | `conv:*:latest` TTL | `86400` |
| `REQUEST_TIMING_ENABLED` | 聊天階段耗時 log | `true` |
| `REDIS_RECONNECT_COOLDOWN_SECONDS` | mock 後限頻重連（/ready），避免每請求重連 | `45` |
| `DAILY_TOKEN_BUDGET_USD` | 全域日預算 | `10.0` |
| `USER_DAILY_TOKEN_BUDGET_USD` | 使用者日預算 | `2.0` |
| `TOKEN_USAGE_LOG` | 用量 JSONL 路徑 | `data/token_usage.jsonl` |
| `MODERATION_ENABLED` | 內容審核 | `true` |
| `MODERATION_CHECK_OUTPUT` | 輸出審核 | `true` |
| `TAVILY_API_KEY` | web_search | 無則備援 |
| `WEB_SEARCH_TIMEOUT` | 搜尋逾時秒 | `12` |
| `WEB_SEARCH_FALLBACK` | DDG 備援 | `true` |
| `MAX_TOOLS_PER_TURN` | 每回合工具上限 | `3` |
| `MAX_TOOL_OUTPUT_CHARS` | 工具輸出截斷 | `6000` |
| `REMINDERS_FILE` | 提醒 JSON | `data/reminders.json` |
| `SUPABASE_VOICE_EVENTS_TABLE` | 語音事件表 | `voice_events` |
| `APP_VERSION` | 健康檢查版本 | `1.0.1` |
| `RAILWAY_GIT_COMMIT_SHA` / `GIT_COMMIT` / `GITHUB_SHA` | 可選，健康檢查回傳 `git_commit`（截短） | 空 |
| `READY_CHECK_SUPABASE_DNS` | `/ready` 是否做 Supabase DNS（非 DB 探測；預設 false） | `false` |
| `LOG_VERBOSE_EXCEPTIONS` | 外部錯誤日誌是否附脫敏短訊息 | `false` |
| `AI_KERNEL_ENABLED` | 啟用 AI Kernel 取代 Legacy 主路徑 | `false` |
| `AI_KERNEL_SHADOW_MODE` | Shadow：背景跑 Kernel，無副作用、不改回應 | `false` |
| `KERNEL_DEBUG_ENABLED` | Debug Trace API | `false` |
| `KERNEL_MAX_AGENT_ITERATIONS` | Agent Loop 迭代上限 | `3` |
| `KERNEL_MAX_TOOL_CALLS` | 每輪工具上限 | `5` |
| `KERNEL_CONTEXT_TOKEN_BUDGET` | Context token 預算（粗估） | `12000` |
| `KERNEL_FALLBACK_TO_LEGACY` | Kernel 致命錯誤回退 Legacy | `true` |
| `KERNEL_DEBUG_SECRET` | Debug API Bearer（優先於 API_SECRET） | 空 |
| `KERNEL_TOOL_ALLOWLIST` | 逗號分隔工具白名單（空=不限制） | 空 |
| `KERNEL_TOOL_BLOCKLIST` | 額外封鎖工具名 | 空 |
| `KERNEL_VOICE_TOOL_RESTRICT` | 語音/車載僅 voice-safe 工具 | `true` |
| `MEMORY_V2_ENABLED` | 啟用 Memory System V2（Strangler；仍寫入 V1 conversation） | `false` |
| `MEMORY_GRAPH_FILE` | V2 記憶圖譜 JSON 路徑 | `data/memory_graph.json` |
| `IDENTITY_STORE_DIR` | Identity Engine 版本庫目錄 | `data/identity` |
| `IDENTITY_UPDATE_MODE` | `candidate`（未達門檻或 staging 預設）/ `formal` | `candidate` |
| `IDENTITY_CONFIDENCE_THRESHOLD` | 正式 Identity 更新最低 confidence | `0.6` |
| `TOKEN_LEDGER_PATH` | Token 會計 JSONL（與訊息正文分離） | `data/token_ledger.jsonl` |
| `TOKEN_LEDGER_ENABLED` | 是否寫入 token ledger | `true` |
| `EMBEDDING_MODEL` | Typed memory / retrieval 共用 embedding 模型 | `text-embedding-3-small` |
| `NIGHT_GROWTH_ENABLED` | 允許 scheduler job 真正執行（預設關；勿多 replica 自動 start） | `false` |
| `NIGHT_GROWTH_INTERNAL_TOKEN` | `POST /internal/night-growth/run` 內部 token | 空則回退 `API_SECRET` |
| `NIGHT_GROWTH_ENDPOINT_ENABLED` | 是否開放內部 Night Growth endpoint | `true` |
| `NIGHT_GROWTH_STORE_DIR` | Night Growth 執行紀錄／lock 目錄 | `data/night_growth` |
| `REFLECTION_INCLUDE_STATUS` | `include_reflection=true` 時回傳 `reflection_status` | `true` |
| `REFLECTION_INCLUDE_WAIT_MS` | 可選 bounded wait（毫秒）；0=立即 pending | `0` |
| `REFLECTION_INCLUDE_WAIT_MAX_MS` | wait 上限 | `1500` |
| `APP_ENV` | 環境標記（staging/production） | 空 |
| `SILENCE_ENGINE_ENABLED` | 靜默引擎主開關（回答路徑切換，**非** sleep） | `false` |
| `SILENCE_ENGINE_MODE` | `observe`（只記錄）/ `shadow`（內部可比較、不改答案）/ `active`（僅 allowlist 可改路徑） | `observe` |
| `SILENCE_ENGINE_ALLOWLIST` | 逗號分隔：`user:<id>`、`conv:<id>`、`ai:<id>` 或裸 id | 空＝無人在 active 放行 |
| `SILENCE_ENGINE_MIN_CONFIDENCE` | 路由最低信心（0–1） | `0.75` |
| `SILENCE_ENGINE_MAX_HYPOTHESES` | C1n 最多假設數（原型 ≤2） | `2` |
| `SILENCE_ENGINE_LOGGING_ENABLED` | 是否打 silence_engine 結構化 log | `true` |

## 前端（Vite）

| 變數 | 用途 |
|------|------|
| `VITE_API_URL` | 後端 API base |
| `VITE_COPILOT_API_URL` | Copilot |
| `VITE_API_SECRET` | 對應後端 API_SECRET |
| `VITE_SUPABASE_URL` | 前端 Auth |
| `VITE_SUPABASE_ANON_KEY` | 前端 Auth |

生產預設見 `frontend/.env.production`（僅 URL，無 key）。

## 測試用假值（CI）

```text
OPENAI_API_KEY=test-key
SUPABASE_URL=http://mock.supabase.local
SUPABASE_ANON_KEY=test-key
SILENCE_ENGINE_ENABLED=false
```

## 變更規則

- **不得**在本階段為圖方便改名既有環境變數
- 新增變數必須寫入本文件與 CHANGELOG
