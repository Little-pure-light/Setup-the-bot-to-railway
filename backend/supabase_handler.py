import os
import logging
from supabase import create_client, Client
from typing import Optional, Any, Tuple

_supabase: Optional[Client] = None
_supabase_fingerprint: Optional[str] = None
_supabase_key_mode: str = "unknown"
logger = logging.getLogger("supabase_handler")

# Task 006 (PR18 review, P0-3):
# The data-plane RPCs (match_memories_v2 / match_memories) are GRANTED to
# service_role ONLY in the forward migration. Backend must therefore prefer
# SUPABASE_SERVICE_ROLE_KEY for its data plane. If only an anon/legacy key is
# available, those RPCs will fail-closed (permission denied) — which is the
# honest, safe outcome. Row isolation is additionally enforced in application
# code and in the SQL body; RLS policies for end-user JWTs are deferred to
# Gate C. get_user_from_token() below is the SEPARATE auth-plane call: it only
# validates a user's JWT and does not depend on the data-plane key privilege.


def _resolve_supabase_credentials() -> Tuple[str, str, str]:
    """
    讀取 Supabase 連線設定。回傳 (url, key, key_mode)。

    金鑰優先序（資料平面）：
      1. SUPABASE_SERVICE_ROLE_KEY  → mode "service_role"（可呼叫記憶 RPC）
      2. SUPABASE_ANON_KEY          → mode "anon"（記憶 RPC 會被拒；僅供相容）
      3. SUPABASE_KEY               → mode "legacy_key"（舊環境）
    """
    url = (os.environ.get("SUPABASE_URL") or "").strip().strip('"').strip("'")

    def _clean(v: Optional[str]) -> str:
        return (v or "").strip().strip('"').strip("'")

    service_key = _clean(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    anon_key = _clean(os.environ.get("SUPABASE_ANON_KEY"))
    legacy_key = _clean(os.environ.get("SUPABASE_KEY"))

    if service_key:
        return url, service_key, "service_role"
    if anon_key:
        return url, anon_key, "anon"
    if legacy_key:
        return url, legacy_key, "legacy_key"
    return url, "", "missing"


def get_supabase_key_mode() -> str:
    """回傳目前資料平面金鑰模式（service_role | anon | legacy_key | missing | unknown）。
    供健康檢查與誠實狀態回報使用；不外洩金鑰內容。"""
    return _supabase_key_mode


def get_supabase() -> Client:
    """獲取 Supabase 客戶端實例（單例；憑證變更時重建）。"""
    global _supabase, _supabase_fingerprint, _supabase_key_mode
    url, key, mode = _resolve_supabase_credentials()
    if not url or not key:
        raise ValueError(
            "❌ 缺少 SUPABASE_URL，或 SUPABASE_SERVICE_ROLE_KEY / "
            "SUPABASE_ANON_KEY / SUPABASE_KEY 環境變數。"
        )

    fingerprint = f"{url}|{mode}|{key[:16]}"
    if _supabase is None or _supabase_fingerprint != fingerprint:
        _supabase = create_client(url, key)
        _supabase_fingerprint = fingerprint
        _supabase_key_mode = mode
        logger.info(
            f"✅ Supabase client ready host={url.split('//')[-1][:40]} key_mode={mode}"
        )
        if mode != "service_role":
            logger.warning(
                "⚠️ Supabase data plane running on key_mode=%s. Memory RPCs "
                "(match_memories_v2) are granted to service_role only and will "
                "be denied. Set SUPABASE_SERVICE_ROLE_KEY before Gate C. "
                "Isolation is application-enforced; RLS/JWT policies deferred.",
                mode,
            )
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
