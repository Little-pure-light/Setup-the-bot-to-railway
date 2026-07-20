# 還原程序（小宸光 AI）

> **狀態：文件完成；完整還原演練 = 需人工驗收**  
> 本文件不得在未實際演練前宣稱「已完成還原」。

## 完整還原檢查清單（人工）

1. [ ] 建立新 Railway Project（或指定既有）
2. [ ] 連接 GitHub Repository，選定穩定 Tag / Commit
3. [ ] 建立 / 還原 Supabase 專案
4. [ ] 啟用 `vector` extension
5. [ ] 匯入 Schema + RPC `match_memories`
6. [ ] 還原表資料（memories / emotional_states / preferences）
7. [ ] 還原 Storage（若有）
8. [ ] 設定環境變數（見 `docs/ENVIRONMENT_VARIABLES.md`）
9. [ ] 啟動後端（`uvicorn main:app --host 0.0.0.0 --port $PORT`）
10. [ ] `GET /live` → `status=ok`
11. [ ] `GET /ready` → `ok` 或可接受的 `degraded`
12. [ ] Smoke：`POST /api/chat`（或前端）
13. [ ] 確認舊記憶可召回（同 `conversation_id` / 登入 user）
14. [ ] 記錄演練日期與結果

## 新建環境最小步驟

### A. 程式

```bash
git checkout vX.Y.Z   # 或穩定 SHA
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### B. Supabase Schema（摘要）

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS xiaochenguang_memories (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT,
  user_id TEXT,
  user_message TEXT,
  assistant_message TEXT,
  embedding VECTOR(1536),
  memory_type TEXT,
  platform TEXT,
  document_content TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  access_count INTEGER DEFAULT 1,
  importance_score FLOAT,
  file_name TEXT,
  ai_id TEXT,
  message_type TEXT
);

CREATE TABLE IF NOT EXISTS emotional_states (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT,
  emotion_type TEXT,
  intensity FLOAT,
  context TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- match_memories RPC：見 README
```

### C. 資料還原

- 使用 `pg_restore` / SQL import / Supabase backup restore
- 驗證：`select count(*) from xiaochenguang_memories;`

### D. 驗證指令

```bash
curl -s $BASE/live
curl -s $BASE/ready
curl -s $BASE/api/health
# chat smoke（需 OPENAI_API_KEY）
```

## Redis 遺失

- 不需還原即可運作
- 上傳中檔案內容需重傳
- 短期上下文清空

## 提醒 JSON 遺失

- 使用者需重新設定提醒
- 標為高風險，見 BACKUP.md

## 回滾與還原的差異

| 情境 | 做法 |
|------|------|
| 壞程式、資料正常 | Railway 切回舊 Commit / Tag（`docs/ROLLBACK.md`） |
| 資料損毀 | 本文件 Supabase 還原 |
| 兩者皆壞 | 先還程式再還資料，再 Smoke |
