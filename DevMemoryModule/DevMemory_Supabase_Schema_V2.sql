-- ============================================
-- XiaoChenGuang 開發者記憶助手 V2 - Supabase Schema
-- ============================================
-- 功能：記錄開發對話、語義搜尋、生成背景包
-- 版本：2.0.0
-- 日期：2025-10-24
-- ============================================

-- ============================================
-- 步驟 0：清理舊版本（避免版本衝突）
-- ============================================

-- 刪除舊版 RPC 函數（如果存在）
DROP FUNCTION IF EXISTS match_dev_logs(vector(1536), int, text, text);
DROP FUNCTION IF EXISTS match_dev_logs(vector(1536), int);

-- ============================================
-- 步驟 1：啟用 pgvector 擴充功能
-- ============================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- 步驟 2：建立 dev_logs 資料表（完整版）
-- ============================================

CREATE TABLE IF NOT EXISTS dev_logs (
    -- 主鍵
    id BIGSERIAL PRIMARY KEY,
    
    -- 開發階段資訊
    phase TEXT NOT NULL,                    -- 開發階段（Phase1, Phase2, Phase3...）
    module TEXT NOT NULL,                   -- 模組名稱
    ai_model TEXT NOT NULL,                 -- AI 模型名稱（GPT-4, Claude...）
    topic TEXT NOT NULL,                    -- 討論主題
    
    -- 對話內容
    user_question TEXT NOT NULL,            -- 使用者問題
    ai_response TEXT NOT NULL,              -- AI 回應
    
    -- 自動生成欄位（用於全文搜尋和摘要）
    content TEXT GENERATED ALWAYS AS (user_question || ' ' || ai_response) STORED,
    
    -- 向量嵌入（用於語義搜尋）
    embedding vector(1536),                 -- OpenAI text-embedding-3-small 的維度
    
    -- 標籤和元數據
    tags TEXT[],                            -- 標籤陣列
    metadata JSONB DEFAULT '{}'::jsonb,     -- 擴充元數據
    
    -- 時間戳記
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- 建立索引（優化查詢效能）
-- ============================================

-- 向量相似度搜尋索引（核心功能）
CREATE INDEX IF NOT EXISTS dev_logs_embedding_idx ON dev_logs USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 常用欄位索引
CREATE INDEX IF NOT EXISTS dev_logs_phase_idx ON dev_logs(phase);
CREATE INDEX IF NOT EXISTS dev_logs_module_idx ON dev_logs(module);
CREATE INDEX IF NOT EXISTS dev_logs_created_at_idx ON dev_logs(created_at DESC);

-- 全文搜尋索引（備用方案 - 使用 simple 配置，因為 Postgres 預設不支援 chinese）
-- 主要依賴向量搜尋，此索引為可選
CREATE INDEX IF NOT EXISTS dev_logs_content_idx ON dev_logs USING GIN(to_tsvector('simple', content));

-- ============================================
-- 步驟 3：建立 RPC 函數 - 向量相似度搜尋（修正版）
-- ============================================

-- 刪除舊版本（如果存在）
DROP FUNCTION IF EXISTS match_dev_logs;

-- 建立新版本（只接受 2 個參數，避免版本衝突）
CREATE OR REPLACE FUNCTION match_dev_logs(
    query_embedding vector(1536),
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id bigint,
    phase text,
    module text,
    ai_model text,
    topic text,
    user_question text,
    ai_response text,
    content text,
    tags text[],
    created_at timestamp with time zone,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT 
        dev_logs.id,
        dev_logs.phase,
        dev_logs.module,
        dev_logs.ai_model,
        dev_logs.topic,
        dev_logs.user_question,
        dev_logs.ai_response,
        dev_logs.content,
        dev_logs.tags,
        dev_logs.created_at,
        1 - (dev_logs.embedding <=> query_embedding) AS similarity
    FROM dev_logs
    WHERE dev_logs.embedding IS NOT NULL
    ORDER BY dev_logs.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- ============================================
-- 步驟 4：建立自動更新 updated_at 的觸發器
-- ============================================

-- 建立觸發器函數
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 建立觸發器
DROP TRIGGER IF EXISTS update_dev_logs_updated_at ON dev_logs;
CREATE TRIGGER update_dev_logs_updated_at
    BEFORE UPDATE ON dev_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 步驟 5：插入測試資料（可選）
-- ============================================

-- 清空測試資料（如果需要重新開始）
-- TRUNCATE TABLE dev_logs RESTART IDENTITY CASCADE;

-- 插入範例記錄
INSERT INTO dev_logs (phase, module, ai_model, topic, user_question, ai_response, tags, embedding)
VALUES 
(
    'Phase1',
    '系統初始化',
    'GPT-4',
    'Supabase 設定',
    '如何在 Supabase 啟用 pgvector？',
    '在 Supabase SQL Editor 執行：CREATE EXTENSION IF NOT EXISTS vector;',
    ARRAY['Supabase', 'pgvector', '設定'],
    NULL  -- embedding 會在後端程式中生成
),
(
    'Phase1',
    '資料庫設計',
    'Claude',
    'Schema 設計',
    'dev_logs 表格需要哪些欄位？',
    '需要 phase, module, ai_model, topic, user_question, ai_response, embedding, tags 等欄位。',
    ARRAY['資料庫', 'Schema', '設計'],
    NULL
),
(
    'Phase2',
    'API 整合',
    'GPT-4',
    'OpenAI Embeddings',
    '如何生成 embedding？',
    '使用 OpenAI API：client.embeddings.create(model="text-embedding-3-small", input=text)',
    ARRAY['OpenAI', 'Embeddings', 'API'],
    NULL
)
ON CONFLICT DO NOTHING;

-- ============================================
-- 步驟 6：授權設定（確保 Supabase 可以存取）
-- ============================================

-- 授予 anon 角色讀取權限（用於 RPC 函數）
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON dev_logs TO anon, authenticated;
GRANT EXECUTE ON FUNCTION match_dev_logs TO anon, authenticated;

-- 授予 authenticated 使用者完整權限
GRANT ALL ON dev_logs TO authenticated;
GRANT ALL ON SEQUENCE dev_logs_id_seq TO authenticated;

-- ============================================
-- 完成！
-- ============================================

-- 驗證建立結果
SELECT 
    '✅ dev_logs 資料表建立成功！' AS status,
    COUNT(*) AS record_count,
    COUNT(DISTINCT phase) AS phase_count,
    COUNT(DISTINCT module) AS module_count
FROM dev_logs;

-- 驗證 RPC 函數
SELECT 
    '✅ match_dev_logs RPC 函數建立成功！' AS status,
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_name = 'match_dev_logs';

-- ============================================
-- 使用說明
-- ============================================

-- 1. 執行此 SQL 腳本（在 Supabase SQL Editor）
-- 2. 確認看到「✅ dev_logs 資料表建立成功！」訊息
-- 3. 確認看到「✅ match_dev_logs RPC 函數建立成功！」訊息
-- 4. 啟動 DevMemory_Streamlit_UI_V2.py 開始使用

-- ============================================
-- 常見問題排查
-- ============================================

-- Q1: 如何檢查 pgvector 是否啟用？
-- A1: SELECT * FROM pg_extension WHERE extname = 'vector';

-- Q2: 如何檢查 RPC 函數是否存在？
-- A2: SELECT routine_name FROM information_schema.routines WHERE routine_name = 'match_dev_logs';

-- Q3: 如何刪除所有記錄重新開始？
-- A3: TRUNCATE TABLE dev_logs RESTART IDENTITY CASCADE;

-- Q4: 如何手動測試 RPC 函數？
-- A4: 需要先生成 embedding，然後：
--     SELECT * FROM match_dev_logs(
--         '[0.1, 0.2, ..., 0.5]'::vector(1536),
--         5
--     );
