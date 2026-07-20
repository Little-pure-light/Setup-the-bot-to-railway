# 備份程序（小宸光 AI）

> 依本 repo 真實結構撰寫。完整還原演練需人工於 Supabase / Railway 控制台執行。

## 1. 程式碼

| 項目 | 位置 |
|------|------|
| 原始碼 | GitHub `Little-pure-light/Setup-the-bot-to-railway` |
| 分支策略 | `main` 正式；功能在 `feature/*` |
| 版本標記 | Git Tag `vMAJOR.MINOR.PATCH`（見 `docs/RELEASE.md`） |
| 部署對應 | Railway 部署 Commit SHA 需記錄於 CHANGELOG |

備份方式：

```bash
git fetch --all --tags
git clone https://github.com/Little-pure-light/Setup-the-bot-to-railway.git
```

## 2. Supabase

### 2.1 預期資料表（程式碼引用）

| 表名 | 用途 | 主要程式 |
|------|------|----------|
| `xiaochenguang_memories` | 對話記憶 + embedding + personality 文件 | `modules/memory_system.py` |
| `emotional_states` | 情緒狀態 | `memory_system.save_emotional_state` |
| `user_preferences` | 人格 / voice_settings | `personality_engine`, `voice_router` |
| `voice_events`（可選） | 語音事件 | `voice_router` |
| `users`（若存在） | 舊 healthcheck 探測 | `healthcheck_router` |

環境變數：`SUPABASE_MEMORIES_TABLE`（預設 `xiaochenguang_memories`）

### 2.2 向量與 RPC

- 擴展：`pgvector`，欄位 `embedding VECTOR(1536)`
- RPC：`match_memories(query_embedding, match_count, conversation_id)`
- 見 README 資料庫章節

### 2.3 Storage

- 檔案上傳：`backend/file_upload.py` → Supabase Storage
- 備份：Supabase Dashboard → Storage 下載，或 `supabase storage` CLI

### 2.4 建議備份步驟（人工）

1. Supabase Dashboard → Database → Backups（若方案支援）或 `pg_dump`
2. 匯出 Schema（含 functions / extensions）
3. 匯出 `xiaochenguang_memories`、`emotional_states`、`user_preferences`
4. 下載 Storage bucket
5. 將檔案存到加密離線位置（**勿提交 Git**）

## 3. Redis

| 用途 | Key 模式（約） | 消失影響 |
|------|----------------|----------|
| 短期對話 | `conv:{id}:latest` | 僅失最近一輪快取；長期記憶仍在 Supabase |
| 上傳暫存 | `upload:{conversation_id}:*` | 需重新上傳檔案/圖片 |
| 提醒 | **預設不在 Redis** | 見下 |

## 4. 提醒資料

`backend/tools/reminder.py` 預設寫入本地：

- 路徑：`data/reminders.json` 或 `REMINDERS_FILE`
- **Railway ephemeral disk 重啟可能遺失** → 高風險
- 備份：若使用，需定期複製 `data/reminders.json` 或改存 Supabase（後續任務）

## 5. 人格與設定檔

| 檔案 | 說明 |
|------|------|
| `profile/user_profile.json` | 小宸光核心人格 |
| Supabase `memory_type=personality` | 學習後人格 |
| `user_preferences.personality_profile` / `voice_settings` | 使用者偏好 |
| `AI_ID` 環境變數 | 預設 `xiaochenguang_v1` |

## 6. Railway

備份項目：

- 服務環境變數清單（Dashboard 匯出，**勿進 Git**）
- 部署的 Commit SHA
- `backend/railway.json` / root start command
- 自訂 domain

## 7. Token 用量本地檔

- `data/token_usage.jsonl` 或 `TOKEN_USAGE_LOG`
- 可選備份；遺失只影響本地用量統計

## 8. 備份頻率建議

| 項目 | 頻率 |
|------|------|
| GitHub | 每次合併 |
| Supabase DB | 每日或變更前 |
| Storage | 每週 |
| 環境變數清單 | 每次變更後更新離線副本 |
