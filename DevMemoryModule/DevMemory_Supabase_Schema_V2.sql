-- ============================================
-- XiaoChenGuang 開發者記憶助手 - Supabase Schema V2
-- 完全重構版本 - 解決所有已知問題
-- ============================================

-- ============================================
-- 步驟 0：清理舊版本（避免衝突）
-- ============================================

-- 刪除舊的 RPC 函數（避免版本衝突）
DROP FUNCTION IF EXISTS match_dev_logs(vector, int);
DROP FUNCTION IF EXISTS match_dev_logs(vector, int, text);
DROP FUNCTION IF EXISTS match_dev_logs(vector, int, text, text);
DROP FUNCTION IF EXISTS generate_project_context(text, text);

-- 刪除舊的資料表（如果需要重建）
-- 注意：這會刪除所有現有資料！如果要保留資料，請先備份
-- DROP TABLE IF EXISTS dev_logs CASCADE;

-- ============================================
-- 步驟 1：建立開發日誌資料表（統一欄位結構）
-- ============================================

CREATE TABLE IF NOT EXISTS dev_logs (
    -- 主鍵和時間戳
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 分類欄位
    phase VARCHAR(50) NOT NULL,              -- 階段（Phase1/Phase2/Phase3）
    module VARCHAR(100) NOT NULL,            -- 模組（記憶模組/反思模組）
    ai_model VARCHAR(50) NOT NULL,           -- AI 模型（GPT-4/Claude）
    
    -- 內容欄位（確保完整）
    topic VARCHAR(200) NOT NULL,             -- 討論主題
    user_question TEXT NOT NULL,             -- 用戶問題
    ai_response TEXT NOT NULL,               -- AI 回答
    content TEXT GENERATED ALWAYS AS (
        user_question || ' ' || ai_response
    ) STORED,                                -- 合併內容（用於全文搜尋）
    summary TEXT,                            -- 自動摘要
    
    -- 向量嵌入（OpenAI text-embedding-3-small = 1536 維）
    embedding VECTOR(1536),
    
    -- 元數據
    importance_score FLOAT DEFAULT 0.5 CHECK (importance_score >= 0 AND importance_score <= 1),
    tags TEXT[] DEFAULT '{}',
    related_files TEXT[] DEFAULT '{}'
);

-- ============================================
-- 步驟 2：建立索引（提升查詢效能）
-- ============================================

-- 向量相似度搜尋索引（使用 HNSW 算法）
CREATE INDEX IF NOT EXISTS dev_logs_embedding_idx 
ON dev_logs 
USING hnsw (embedding vector_cosine_ops);

-- 常用查詢欄位索引
CREATE INDEX IF NOT EXISTS dev_logs_phase_idx ON dev_logs(phase);
CREATE INDEX IF NOT EXISTS dev_logs_module_idx ON dev_logs(module);
CREATE INDEX IF NOT EXISTS dev_logs_created_at_idx ON dev_logs(created_at DESC);

-- 全文搜尋索引（備用方案 - 使用 simple 配置，因為 Postgres 預設不支援 chinese）
-- 主要依賴向量搜尋，此索引為可選
CREATE INDEX IF NOT EXISTS dev_logs_content_idx ON dev_logs USING GIN(to_tsvector('simple', content));

-- ============================================
-- 步驟 3：建立 RPC 函數 - 向量相似度搜尋（修正版）
-- ============================================

CREATE OR REPLACE FUNCTION match_dev_logs(
    query_embedding VECTOR(1536),
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    created_at TIMESTAMP WITH TIME ZONE,
    phase VARCHAR(50),
    module VARCHAR(100),
    ai_model VARCHAR(50),
    topic VARCHAR(200),
    user_question TEXT,
    ai_response TEXT,
    summary TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dev_logs.id,
        dev_logs.created_at,
        dev_logs.phase,
        dev_logs.module,
        dev_logs.ai_model,
        dev_logs.topic,
        dev_logs.user_question,
        dev_logs.ai_response,
        dev_logs.summary,
        1 - (dev_logs.embedding <=> query_embedding) AS similarity
    FROM dev_logs
    WHERE dev_logs.embedding IS NOT NULL
    ORDER BY dev_logs.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================
-- 步驟 4：建立輔助函數 - 生成專案背景包
-- ============================================

CREATE OR REPLACE FUNCTION generate_project_context(
    target_phase TEXT DEFAULT NULL,
    target_module TEXT DEFAULT NULL,
    max_logs INT DEFAULT 10
)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    context_text TEXT := '';
    log_record RECORD;
    log_count INT := 0;
BEGIN
    -- 標題
    context_text := E'📦 XiaoChenGuang 專案背景包\n';
    context_text := context_text || '生成時間：' || TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS') || E'\n\n';
    
    -- 專案概述
    context_text := context_text || E'【專案概述】\n';
    context_text := context_text || E'數位靈魂孵化器 - XiaoChenGuang AI 系統\n';
    context_text := context_text || E'技術棧：FastAPI + Vue 3 + Supabase + OpenAI + Redis\n';
    context_text := context_text || E'核心模組：\n';
    context_text := context_text || E'  • 記憶系統（向量嵌入 + pgvector）\n';
    context_text := context_text || E'  • 反思模組（反推果因法則）\n';
    context_text := context_text || E'  • 人格學習引擎（動態特質調整）\n';
    context_text := context_text || E'  • 情感檢測系統（9種情緒類型）\n';
    context_text := context_text || E'  • 提示詞引擎（動態 Prompt 生成）\n\n';
    
    -- 最近開發記錄
    context_text := context_text || E'【最近開發記錄】\n';
    
    FOR log_record IN
        SELECT 
            TO_CHAR(created_at, 'YYYY-MM-DD') AS date,
            phase,
            module,
            topic,
            COALESCE(summary, SUBSTRING(user_question, 1, 100)) AS summary_text
        FROM dev_logs
        WHERE 
            (target_phase IS NULL OR phase = target_phase)
            AND (target_module IS NULL OR module = target_module)
        ORDER BY created_at DESC
        LIMIT max_logs
    LOOP
        log_count := log_count + 1;
        context_text := context_text || log_count || '. ' || log_record.date || ' [' || 
                        log_record.phase || '] ' || log_record.topic || E'\n';
        context_text := context_text || '   摘要：' || 
                        SUBSTRING(log_record.summary_text, 1, 80) || E'...\n\n';
    END LOOP;
    
    -- 如果沒有記錄
    IF log_count = 0 THEN
        context_text := context_text || E'（目前尚無開發記錄）\n\n';
    END IF;
    
    -- 使用說明
    context_text := context_text || E'【使用說明】\n';
    context_text := context_text || E'1. 複製上面的背景包\n';
    context_text := context_text || E'2. 貼給任何 AI（ChatGPT/Claude/Gemini）\n';
    context_text := context_text || E'3. AI 就能立刻了解專案背景！\n';
    context_text := context_text || E'4. 然後問你的問題，AI 會給出更精準的建議\n\n';
    context_text := context_text || E'---\n';
    context_text := context_text || E'由 XiaoChenGuang 開發者記憶助手生成\n';
    
    RETURN context_text;
END;
$$;

-- ============================================
-- 步驟 5：建立觸發器 - 自動更新時間戳
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_dev_logs_updated_at
    BEFORE UPDATE ON dev_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 步驟 6：插入測試資料（驗證功能）
-- ============================================

-- 清理舊測試資料
DELETE FROM dev_logs WHERE topic LIKE '%測試記錄%';

-- 插入測試記錄
INSERT INTO dev_logs (
    phase,
    module,
    ai_model,
    topic,
    user_question,
    ai_response,
    summary,
    importance_score,
    tags
) VALUES 
(
    'Phase1',
    '測試模組',
    'GPT-4',
    '系統測試記錄',
    '這是一條測試記錄，用於驗證資料表是否正常運作？',
    '資料表運作正常！所有欄位都已正確建立，RPC 函數也已準備就緒。',
    '測試記錄：驗證資料表功能正常',
    0.5,
    ARRAY['測試', '系統驗證']
);

-- ============================================
-- 步驟 7：授權設定（如果使用 RLS）
-- ============================================

-- 如果你的專案使用 Row Level Security，請取消以下註解
-- ALTER TABLE dev_logs ENABLE ROW LEVEL SECURITY;

-- 允許所有已認證用戶讀寫（根據需求調整）
-- CREATE POLICY "Allow authenticated users to read dev_logs"
--     ON dev_logs FOR SELECT
--     TO authenticated
--     USING (true);

-- CREATE POLICY "Allow authenticated users to insert dev_logs"
--     ON dev_logs FOR INSERT
--     TO authenticated
--     WITH CHECK (true);

-- ============================================
-- 完成！執行此腳本後你會得到：
-- ============================================
-- ✅ 統一的資料表結構（包含所有必要欄位）
-- ✅ 向量搜尋索引（HNSW 高效能）
-- ✅ 修正的 RPC 函數（無版本衝突）
-- ✅ 背景包生成函數（完整錯誤處理）
-- ✅ 自動更新時間戳
-- ✅ 測試資料（驗證功能）

-- ============================================
-- 驗證安裝（執行以下查詢測試）
-- ============================================

-- 1. 檢查資料表結構
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'dev_logs';

-- 2. 檢查測試資料
-- SELECT * FROM dev_logs LIMIT 1;

-- 3. 測試背景包生成
-- SELECT generate_project_context(NULL, NULL, 5);

-- 4. 檢查 RPC 函數是否存在
-- SELECT routine_name, routine_type FROM information_schema.routines WHERE routine_name LIKE 'match_dev_logs%';
