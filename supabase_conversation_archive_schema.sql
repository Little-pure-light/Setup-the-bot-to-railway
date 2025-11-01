-- =====================================================
-- Supabase 對話封存表結構
-- XiaoChenGuang AI System - Conversation Archive Table
-- =====================================================

-- 建立對話封存表
CREATE TABLE IF NOT EXISTS conversation_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'default_user',
    ipfs_cid TEXT NOT NULL,
    gateway_url TEXT,
    message_count INTEGER DEFAULT 0,
    attachment_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 建立索引以加速查詢
CREATE INDEX IF NOT EXISTS idx_conversation_archive_conversation_id 
    ON conversation_archive(conversation_id);

CREATE INDEX IF NOT EXISTS idx_conversation_archive_user_id 
    ON conversation_archive(user_id);

CREATE INDEX IF NOT EXISTS idx_conversation_archive_created_at 
    ON conversation_archive(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversation_archive_ipfs_cid 
    ON conversation_archive(ipfs_cid);

-- 添加註釋
COMMENT ON TABLE conversation_archive IS '對話封存記錄表 - 儲存上傳到 IPFS 的對話 CID';
COMMENT ON COLUMN conversation_archive.id IS '唯一識別碼';
COMMENT ON COLUMN conversation_archive.conversation_id IS '對話 ID（對應 memories 表）';
COMMENT ON COLUMN conversation_archive.user_id IS '使用者 ID';
COMMENT ON COLUMN conversation_archive.ipfs_cid IS 'IPFS 內容識別符（Pinata）';
COMMENT ON COLUMN conversation_archive.gateway_url IS 'IPFS Gateway 存取網址';
COMMENT ON COLUMN conversation_archive.message_count IS '封存的訊息數量';
COMMENT ON COLUMN conversation_archive.attachment_count IS '封存的附件數量';
COMMENT ON COLUMN conversation_archive.created_at IS '封存建立時間';
COMMENT ON COLUMN conversation_archive.updated_at IS '最後更新時間';

-- 啟用 Row Level Security (RLS)
ALTER TABLE conversation_archive ENABLE ROW LEVEL SECURITY;

-- 建立 RLS 政策（允許所有操作，可根據需求調整）
CREATE POLICY "允許所有使用者讀取封存記錄" ON conversation_archive
    FOR SELECT USING (true);

CREATE POLICY "允許所有使用者新增封存記錄" ON conversation_archive
    FOR INSERT WITH CHECK (true);

-- 自動更新 updated_at 的觸發器
CREATE OR REPLACE FUNCTION update_conversation_archive_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER conversation_archive_updated_at_trigger
    BEFORE UPDATE ON conversation_archive
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_archive_updated_at();

-- 完成訊息
SELECT '✅ conversation_archive 表已成功建立！' AS result;
