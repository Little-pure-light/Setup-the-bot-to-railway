# Supabase 資料庫設置指南

## 概述
小宸光 AI 靈魂系統需要兩個 Supabase 資料表來儲存記憶與情緒狀態。

## 必要資料表

### 1. xiaochenguang_memories 表格

此表格儲存所有對話記憶與向量嵌入。

```sql
CREATE TABLE xiaochenguang_memories (
    id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    user_id TEXT,
    ai_id TEXT DEFAULT 'xiaochenguang_v1',
    memory_type TEXT DEFAULT 'conversation',
    user_message TEXT,
    assistant_mes TEXT,
    embedding VECTOR(1536),
    importance_score FLOAT DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    file_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 為對話查詢創建索引
CREATE INDEX idx_conversation_id ON xiaochenguang_memories(conversation_id);
CREATE INDEX idx_memory_type ON xiaochenguang_memories(memory_type);
CREATE INDEX idx_created_at ON xiaochenguang_memories(created_at DESC);
```

### 2. emotional_states 表格

此表格追蹤用戶的情緒狀態歷史。

```sql
CREATE TABLE emotional_states (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    ai_id TEXT DEFAULT 'xiaochenguang_v1',
    emotion TEXT NOT NULL,
    intensity FLOAT,
    confidence FLOAT,
    context TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 為用戶情緒查詢創建索引
CREATE INDEX idx_user_emotion ON emotional_states(user_id, timestamp DESC);
```

### 3. 向量搜尋函數 (RPC)

為了實現記憶檢索功能,需要創建向量相似度搜尋函數:

```sql
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_conversation_id TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    conversation_id TEXT,
    user_message TEXT,
    assistant_mes TEXT,
    importance_score FLOAT,
    access_count INTEGER,
    similarity FLOAT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.conversation_id,
        m.user_message,
        m.assistant_mes,
        m.importance_score,
        m.access_count,
        1 - (m.embedding <=> query_embedding) AS similarity,
        m.created_at
    FROM xiaochenguang_memories m
    WHERE 
        m.memory_type = 'conversation'
        AND (filter_conversation_id IS NULL OR m.conversation_id = filter_conversation_id)
        AND 1 - (m.embedding <=> query_embedding) > match_threshold
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

## Supabase Storage 設置

### 創建檔案儲存桶

在 Supabase Storage 中創建一個 bucket:

1. 進入 Supabase Dashboard → Storage
2. 創建新 bucket,命名為: `xiaochenguang_files`
3. 設置權限為 Public 或 Private (視需求而定)

```sql
-- 如果使用 SQL 創建
INSERT INTO storage.buckets (id, name, public)
VALUES ('xiaochenguang_files', 'xiaochenguang_files', true);
```

## 環境變數確認

確保以下環境變數已在 Replit Secrets 中設置:

- `SUPABASE_URL`: 你的 Supabase 專案 URL
- `SUPABASE_KEY`: Supabase 服務金鑰 (service_role key)
- `OPENAI_API_KEY`: OpenAI API 金鑰
- `SUPABASE_MEMORIES_TABLE`: `xiaochenguang_memories` (可選,預設值)
- `AI_ID`: `xiaochenguang_v1` (可選,預設值)

## 驗證設置

### 測試資料表連接

```bash
# 在 Replit Shell 中執行
curl -X GET "http://localhost:8000/api/memories/test_conv_id?limit=5"
```

### 測試檔案上傳

使用前端介面的「上傳檔案」按鈕測試 Supabase Storage 功能。

## 常見問題排查

### 錯誤: "column xiaochenguang_memories.assistant_mes does not exist"

**原因**: 資料表欄位名稱不匹配
**解決方案**: 
1. 確認資料表中的欄位名稱為 `assistant_mes` (不是 `assistant_message`)
2. 執行上述 CREATE TABLE 語句重建資料表
3. 或執行 ALTER TABLE 修改欄位名稱:

```sql
-- 如果你的欄位是 assistant_message,需要重命名
ALTER TABLE xiaochenguang_memories 
RENAME COLUMN assistant_message TO assistant_mes;
```

### 錯誤: Vector 類型不存在

**原因**: 未啟用 pgvector 擴充
**解決方案**:
1. 進入 Supabase Dashboard → Database → Extensions
2. 啟用 `vector` 擴充
3. 或執行 SQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 記憶檢索無結果

**原因**: RPC 函數未創建或向量嵌入未生成
**解決方案**:
1. 確認 `match_memories` 函數已創建
2. 確認對話已正常儲存並生成 embedding
3. 檢查後端日誌查看詳細錯誤

## 資料遷移

如果你已有舊的資料表結構,可以使用以下腳本遷移:

```sql
-- 備份舊資料
CREATE TABLE xiaochenguang_memories_backup AS 
SELECT * FROM xiaochenguang_memories;

-- 重建新資料表 (先刪除舊表)
DROP TABLE xiaochenguang_memories;

-- 執行上面的 CREATE TABLE 語句
-- ...

-- 恢復資料 (視欄位名稱調整)
INSERT INTO xiaochenguang_memories 
SELECT * FROM xiaochenguang_memories_backup;
```

---

## 完成後

設置完成後,重啟 Backend API workflow,系統應能正常運作。
