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
| `SUPABASE_VOICE_EVENTS_TABLE` | 語音事件表（Task008-002：**目前保留但停用**，端點不讀此變數、不寫 DB；**請勿設定**。未來如需事件分析須另立具 schema/RLS/隱私契約的 opt-in Task） | 停用（勿設） |
| `APP_VERSION` | 健康檢查版本 | `1.0.1` |
| `RAILWAY_GIT_COMMIT_SHA` / `GIT_COMMIT` / `GITHUB_SHA` | 可選，健康檢查回傳 `git_commit`（截短） | 空 |
| `READY_CHECK_SUPABASE_DNS` | `/ready` 是否做 Supabase DNS（非 DB 探測；預設 false） | `false` |
| `LOG_VERBOSE_EXCEPTIONS` | 外部錯誤日誌是否附脫敏短訊息 | `false` |
| `MEMORY_RECALL_DIAGNOSTICS` | 記憶召回去敏診斷：開啟時每次召回多輸出一行「最後注入的 ≤3 筆候選」之去敏明細（12-hex fingerprint + 來源 + 四捨五入分數），用於分辨「答案記憶未被選入」與「已注入仍查無」。**後端限定、預設關閉**；不改變召回/排序/回應/效能 | `false` |
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
| `NIGHT_GROWTH_ENABLED` | 允許任何非 dry-run Night Growth 執行（預設關；勿多 replica 自動 start） | `false` |
| `NIGHT_GROWTH_INTERNAL_TOKEN` | `POST /internal/night-growth/run` 內部 token | 空則回退 `API_SECRET` |
| `NIGHT_GROWTH_ENDPOINT_ENABLED` | 是否開放內部 Night Growth endpoint | `true` |
| `NIGHT_GROWTH_STORE_DIR` | Night Growth 執行紀錄／lock 目錄 | `data/night_growth` |
| `NIGHT_GROWTH_MAX_TURNS` | 每次最多處理 turn 數（硬上限 200） | `20` |
| `NIGHT_GROWTH_MAX_CONVERSATIONS` | 每次最多處理不同 conversation 數（硬上限 50） | `5` |
| `NIGHT_GROWTH_MAX_INPUT_TOKENS` | 每次輸入 token 粗估上限（硬上限 100000；本地字元估算，不呼叫 API） | `12000` |
| `REFLECTION_INCLUDE_STATUS` | `include_reflection=true` 時回傳 `reflection_status` | `true` |
| `REFLECTION_INCLUDE_WAIT_MS` | 可選 bounded wait（毫秒）；0=立即 pending | `0` |
| `REFLECTION_INCLUDE_WAIT_MAX_MS` | wait 上限 | `1500` |
| `APP_ENV` | 環境標記（staging/production） | 空 |
| `SILENCE_ENGINE_ENABLED` | 靜默引擎主開關（回答路徑切換，**非** sleep） | `false` |
| `SILENCE_ENGINE_MODE` | `observe`（只記錄）/ `shadow`（內部可比較、不改答案）/ `active`（僅 allowlist 可改路徑） | `observe` |
| `SILENCE_ENGINE_ALLOWLIST` | 逗號分隔：`user:<id>`、`conv:<id>`、`ai:<id>`、`client:<id>` 或裸 id（裸 id 不含 client） | 空＝無人在 active 放行 |
| `SILENCE_ENGINE_MIN_CONFIDENCE` | 路由最低信心（0–1） | `0.75` |
| `SILENCE_ENGINE_MAX_HYPOTHESES` | C1n 最多假設數（原型 ≤2） | `2` |
| `SILENCE_ENGINE_LOGGING_ENABLED` | 是否打 silence_engine 結構化 log | `true` |

## MEMORY_RECALL_DIAGNOSTICS（去敏召回診斷）

- **用途**：診斷跨對話召回為何漏掉某筆記憶。開啟時，`_rank_candidates()` 在既有
  `recall pool/distinct/injected` 計數行之外，額外輸出一行 `recall_diag`，只列出
  **最後真正注入 prompt 的 ≤3 筆**候選：`slot`、不可逆 `fp`（`SHA-256(user + 分隔 + assistant)` 前 12 個小寫 hex）、
  `src`（`semantic` / `owner_fallback`）、四捨五入的 `cos`／`overlap`／`rel`／`mmr`。
- **預設值**：`false`。只接受明確 truthy（`1`/`true`/`yes`/`on`，大小寫忽略）；其餘一律關閉。
  缺值、錯值或診斷輸出本身發生例外時 **fail-safe**，不影響召回與聊天。
- **後端限定**：不得放入 `VITE_*` 或前端。
- **隱私邊界**：只輸出 fingerprint 與分數；**不輸出**原始訊息、`user_id`、`ai_id`、
  `conversation_id`、row id、embedding、JWT、Authorization 或任何 secret。fingerprint 僅供
  一次性對照，不作身分驗證、資料 owner 或長期追蹤。
- **不改變行為**：候選集、排序、MMR、去重、tie-break、注入筆數與回傳 rows／順序，
  在開關 `true`／`false` 下完全一致；僅多印一行日誌。
- **正式環境使用**：只可短時開啟、擷取需要的 `recall_diag` 後**立即關閉**，並核對部署健康
  （`/ready`、`/health`）。不建議長期開啟。
- **回滾**：revert 本 PR 的單一 commit 即可完全移除本能力。

## 前端（Vite）

| 變數 | 用途 |
|------|------|
| `VITE_API_URL` | 後端 API base |
| `VITE_COPILOT_API_URL` | Copilot |
| `VITE_API_SECRET` | 對應後端 API_SECRET（**不建議**；優先 Supabase JWT） |
| `VITE_SUPABASE_URL` | 前端 Auth |
| `VITE_SUPABASE_ANON_KEY` | 前端 Auth |
| `VITE_CLIENT_ID` | 前端入口標記（如 `cloudflare-test`）；空＝不送標記。**非 secret、非授權** |

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
