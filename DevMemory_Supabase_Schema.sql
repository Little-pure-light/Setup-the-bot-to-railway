-- 開發者記憶模組 - Supabase 資料表建立腳本
-- 用途：儲存你與各種 AI 討論 XiaoChenGuang 專案的對話記錄
-- 完美契合現有的靈魂孵化器架構

-- ============================================
-- 1. 建立開發日誌資料表
-- ============================================
CREATE TABLE IF NOT EXISTS dev_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 基本資訊
    phase VARCHAR(50),              -- 階段標籤（Phase1/Phase2/Phase3...）
    module VARCHAR(100),            -- 模組名稱（記憶模組/反思模組...）
    ai_model VARCHAR(50),           -- 使用的 AI 模型（GPT-4/Claude/Gemini）
    
    -- 對話內容
    topic VARCHAR(200),             -- 討論主題
    user_question TEXT,             -- 你的問題
    ai_response TEXT,               -- AI 的回答
    summary TEXT,                   -- 自動生成的摘要
    
    -- 向量嵌入（用於語義搜尋，跟你現有的 memories 資料表一樣）
    embedding VECTOR(1536),         -- OpenAI text-embedding-3-small 的向量
    
    -- 元數據
    importance_score FLOAT DEFAULT 0.5,  -- 重要性評分（0-1）
    tags TEXT[],                         -- 標籤陣列
    related_files TEXT[],                -- 相關檔案路徑
    
    -- 索引（加速搜尋）
    CONSTRAINT dev_logs_pkey PRIMARY KEY (id)
);

-- ============================================
-- 2. 建立向量相似度搜尋索引
-- ============================================
-- 使用 HNSW 索引（跟你現有的 memories 資料表一樣）
CREATE INDEX IF NOT EXISTS dev_logs_embedding_idx 
ON dev_logs 
USING hnsw (embedding vector_cosine_ops);

-- ============================================
-- 3. 建立 RPC 函數：向量相似度搜尋
-- ============================================
-- 功能：根據問題文本，找出最相關的開發日誌
-- 使用方式：SELECT * FROM match_dev_logs('反思模組測試', 5);

CREATE OR REPLACE FUNCTION match_dev_logs(
    query_embedding VECTOR(1536),
    match_count INT DEFAULT 5,
    filter_phase TEXT DEFAULT NULL,
    filter_module TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    created_at TIMESTAMP WITH TIME ZONE,
    phase VARCHAR(50),
    module VARCHAR(100),
    topic VARCHAR(200),
    summary TEXT,
    user_question TEXT,
    ai_response TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dev_logs.id,
        dev_logs.created_at,
        dev_logs.phase,
        dev_logs.module,
        dev_logs.topic,
        dev_logs.summary,
        dev_logs.user_question,
        dev_logs.ai_response,
        1 - (dev_logs.embedding <=> query_embedding) AS similarity
    FROM dev_logs
    WHERE 
        (filter_phase IS NULL OR dev_logs.phase = filter_phase)
        AND (filter_module IS NULL OR dev_logs.module = filter_module)
    ORDER BY dev_logs.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================
-- 4. 建立輔助函數：生成專案背景包
-- ============================================
-- 功能：根據階段/模組，自動生成完整的專案背景摘要
-- 使用方式：SELECT generate_project_context('Phase3', NULL);

CREATE OR REPLACE FUNCTION generate_project_context(
    target_phase TEXT DEFAULT NULL,
    target_module TEXT DEFAULT NULL
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    context_text TEXT := '';
    log_record RECORD;
BEGIN
    -- 標題
    context_text := E'📦 XiaoChenGuang 專案背景包\n';
    context_text := context_text || '生成時間：' || NOW()::TEXT || E'\n\n';
    
    -- 專案概述
    context_text := context_text || E'【專案概述】\n';
    context_text := context_text || E'數位靈魂孵化器 - XiaoChenGuang AI 系統\n';
    context_text := context_text || E'- 記憶模組（向量嵌入 + pgvector）\n';
    context_text := context_text || E'- 反思模組（反推果因法則）\n';
    context_text := context_text || E'- 行為調節模組（人格向量）\n';
    context_text := context_text || E'- 情感檢測系統（9種情緒）\n\n';
    
    -- 最近開發記錄
    context_text := context_text || E'【最近開發記錄】\n';
    
    FOR log_record IN
        SELECT 
            created_at::DATE AS date,
            phase,
            module,
            topic,
            summary
        FROM dev_logs
        WHERE 
            (target_phase IS NULL OR phase = target_phase)
            AND (target_module IS NULL OR module = target_module)
        ORDER BY created_at DESC
        LIMIT 10
    LOOP
        context_text := context_text || '- ' || log_record.date::TEXT || ' [' || 
                        COALESCE(log_record.phase, '通用') || '] ' || 
                        log_record.topic || E'\n';
        context_text := context_text || '  摘要：' || 
                        SUBSTRING(log_record.summary, 1, 100) || E'...\n';
    END LOOP;
    
    context_text := context_text || E'\n【使用說明】\n';
    context_text := context_text || E'請將此背景包複製貼給任何 AI（ChatGPT/Claude/Gemini）\n';
    context_text := context_text || E'AI 就能立刻了解專案背景，繼續協助開發！\n';
    
    RETURN context_text;
END;
$$;

-- ============================================
-- 5. 建立示例資料（測試用）
-- ============================================
-- 插入一條測試記錄，確保資料表運作正常

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
) VALUES (
    'Phase3',
    '反思模組',
    'GPT-4',
    '反思循環閉環測試',
    '如何確認反思模組正確影響人格向量？',
    '需要檢查三個關鍵點：1. 反思結果是否正確提取改進建議...',
    '討論了反思循環的驗證方法，包含人格向量調整機制的測試流程。',
    0.9,
    ARRAY['測試', '反思模組', 'Phase3']
);

-- ============================================
-- 6. 授權設定（根據你的 Supabase 設定調整）
-- ============================================
-- 如果你使用 Row Level Security (RLS)，請根據需求設定權限
-- ALTER TABLE dev_logs ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 完成！
-- ============================================
-- 執行此腳本後，你的 Supabase 就會有：
-- ✅ dev_logs 資料表（儲存開發日誌）
-- ✅ 向量相似度搜尋索引（快速查詢）
-- ✅ match_dev_logs() 函數（語義搜尋）
-- ✅ generate_project_context() 函數（生成背景包）
