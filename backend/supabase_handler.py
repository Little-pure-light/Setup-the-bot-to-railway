import os
import logging
from supabase import create_client, Client
from typing import Optional, Any, Tuple

_supabase: Optional[Client] = None
_supabase_fingerprint: Optional[str] = None
_supabase_key_mode: str = "unknown"
logger = logging.getLogger("supabase_handler")

# Task 006 (PR18 review, P0-3; C7 comment cleanup):
# The forward migration is EXPAND-ONLY: it creates and GRANTs ONLY the new
# match_memories_v2 to service_role. It does NOT create, grant or alter the
# legacy match_memories (which is not part of the current contract). Backend
# must therefore prefer
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
      2. SUPABASE_SECRET_KEY        → mode "secret"（現代後端金鑰，等同 elevated）
      3. SUPABASE_ANON_KEY          → mode "anon"（記憶 RPC 會被拒；僅供相容）
      4. SUPABASE_KEY               → mode "legacy"（舊環境）
    """
    url = (os.environ.get("SUPABASE_URL") or "").strip().strip('"').strip("'")

    def _clean(v: Optional[str]) -> str:
        return (v or "").strip().strip('"').strip("'")

    # Precedence (elevated backend data-plane first):
    #   1. SUPABASE_SERVICE_ROLE_KEY  → "service_role" (classic elevated)
    #   2. SUPABASE_SECRET_KEY        → "secret"        (modern elevated, sb_secret_...)
    #   3. SUPABASE_ANON_KEY          → "anon"
    #   4. SUPABASE_KEY               → "legacy"
    service_key = _clean(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    secret_key = _clean(os.environ.get("SUPABASE_SECRET_KEY"))
    anon_key = _clean(os.environ.get("SUPABASE_ANON_KEY"))
    legacy_key = _clean(os.environ.get("SUPABASE_KEY"))

    if service_key:
        return url, service_key, "service_role"
    if secret_key:
        return url, secret_key, "secret"
    if anon_key:
        return url, anon_key, "anon"
    if legacy_key:
        return url, legacy_key, "legacy"
    return url, "", "missing"


# Elevated backend modes that can call service_role-granted RPCs (match_memories_v2).
ELEVATED_KEY_MODES = ("service_role", "secret")


def resolved_key_mode() -> str:
    """Current data-plane key mode from the ENVIRONMENT (no client creation, no secret).
    Values: service_role | secret | anon | legacy | missing. For health/readiness."""
    return _resolve_supabase_credentials()[2]


def is_backend_elevated() -> bool:
    """True when the env provides an elevated backend key (service_role or secret)."""
    return resolved_key_mode() in ELEVATED_KEY_MODES


def get_supabase_key_mode() -> str:
    """回傳最近建立之 client 的資料平面金鑰模式（快取）；未建立前為 unknown。
    若要以環境即時判斷請用 resolved_key_mode()。不外洩金鑰內容。"""
    return _supabase_key_mode


def get_supabase() -> Client:
    """獲取 Supabase 客戶端實例（單例；憑證變更時重建）。"""
    global _supabase, _supabase_fingerprint, _supabase_key_mode
    url, key, mode = _resolve_supabase_credentials()
    if not url or not key:
        raise ValueError(
            "❌ 缺少 SUPABASE_URL，或 SUPABASE_SERVICE_ROLE_KEY / SUPABASE_SECRET_KEY / "
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
        if mode not in ELEVATED_KEY_MODES:
            logger.warning(
                "⚠️ Supabase data plane running on key_mode=%s. Memory RPCs "
                "(match_memories_v2) are granted to service_role only and will "
                "be denied. Set an elevated backend key (SUPABASE_SERVICE_ROLE_KEY "
                "or SUPABASE_SECRET_KEY) before Gate C. "
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
