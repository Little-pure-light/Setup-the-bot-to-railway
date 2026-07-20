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
| `API_SECRET` | 保護 `/api/*` | 空=不啟用 |
| `AI_ID` | 預設 AI 實例 | `xiaochenguang_v1` |
| `SUPABASE_MEMORIES_TABLE` | 記憶表名 | `xiaochenguang_memories` |
| `OPENAI_ORG_ID` / `OPENAI_PROJECT_ID` | OpenAI 組織 | 空 |
| `REDIS_URL` / `REDIS_HOST` | Redis | 無則 mock/略過 |
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
```

## 變更規則

- **不得**在本階段為圖方便改名既有環境變數
- 新增變數必須寫入本文件與 CHANGELOG
