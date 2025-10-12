# backend/supabase_handler.py - 請完整貼上以下代碼

import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

_supabase: Client = None # 單例變數，只建立一次

def get_supabase() -> Client:
    """獲取 Supabase 客戶端實例（單例模式）。"""
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            # 啟動檢查：確保環境變數存在
            raise ValueError("❌ 缺少 SUPABASE_URL 或 SUPABASE_ANON_KEY 環境變數。")
        _supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase
