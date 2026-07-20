import os
import logging
from supabase import create_client, Client
from typing import Optional, Any, Tuple

_supabase: Optional[Client] = None
_supabase_fingerprint: Optional[str] = None
logger = logging.getLogger("supabase_handler")


def _resolve_supabase_credentials() -> Tuple[str, str]:
    """
    讀取 Supabase 連線設定。
    相容 SUPABASE_ANON_KEY / SUPABASE_KEY（舊環境常用後者）。
    """
    url = (os.environ.get("SUPABASE_URL") or "").strip().strip('"').strip("'")
    key = (
        os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
        or ""
    ).strip().strip('"').strip("'")
    return url, key


def get_supabase() -> Client:
    """獲取 Supabase 客戶端實例（單例；憑證變更時重建）。"""
    global _supabase, _supabase_fingerprint
    url, key = _resolve_supabase_credentials()
    if not url or not key:
        raise ValueError(
            "❌ 缺少 SUPABASE_URL，或 SUPABASE_ANON_KEY / SUPABASE_KEY 環境變數。"
        )

    fingerprint = f"{url}|{key[:16]}"
    if _supabase is None or _supabase_fingerprint != fingerprint:
        _supabase = create_client(url, key)
        _supabase_fingerprint = fingerprint
        logger.info(f"✅ Supabase client ready host={url.split('//')[-1][:40]}")
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


def reset_supabase_client() -> None:
    """測試用：清除單例，強制下次重新建立 client。"""
    global _supabase, _supabase_fingerprint
    _supabase = None
    _supabase_fingerprint = None
