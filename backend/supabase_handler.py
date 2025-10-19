import os
from supabase import create_client, Client
from typing import Optional

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

_supabase: Optional[Client] = None

def get_supabase() -> Client:
    """獲取 Supabase 客戶端實例（單例模式）。"""
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise ValueError("❌ 缺少 SUPABASE_URL 或 SUPABASE_ANON_KEY 環境變數。")
        _supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase
