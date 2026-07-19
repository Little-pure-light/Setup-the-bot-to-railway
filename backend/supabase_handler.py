import os
import logging
from supabase import create_client, Client
from typing import Optional, Any

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

_supabase: Optional[Client] = None
logger = logging.getLogger("supabase_handler")


def get_supabase() -> Client:
    """獲取 Supabase 客戶端實例（單例模式）。"""
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise ValueError("❌ 缺少 SUPABASE_URL 或 SUPABASE_ANON_KEY 環境變數。")
        _supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase


def get_user_from_token(access_token: str) -> Optional[Any]:
    """
    以 Supabase Auth JWT 驗證並取得使用者。
    成功回傳 user 物件；失敗回傳 None。
    """
    if not access_token or not access_token.strip():
        return None
    try:
        client = get_supabase()
        result = client.auth.get_user(access_token.strip())
        return getattr(result, "user", None)
    except Exception as e:
        logger.warning(f"⚠️ Supabase JWT 驗證失敗: {e}")
        return None
