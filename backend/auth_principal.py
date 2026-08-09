"""
Task010-001 — 共用 JWT principal 依賴（登入者唯讀記憶中心 owner 隔離）。

原則：
- 重用既有 Supabase JWT 驗證（`get_user_from_token`）；不自行解析 token、不信任未驗證 claims、
  不擴大 token 接受範圍、不改全域 middleware。
- 缺／格式錯／無效／過期 JWT 一律 401。
- API_SECRET-only 不構成真人 principal：`get_user_from_token` 對非 Supabase JWT 會回 None → 401。
- helper 與錯誤訊息不 log token、user id、email 或 raw exception。
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from backend.supabase_handler import get_user_from_token


def extract_bearer(authorization: Optional[str]) -> str:
    """從 Authorization header 取出 Bearer token；缺少或格式錯誤一律 401（不回顯 header 內容）。"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=401,
            detail="Authorization 格式錯誤，請使用 Bearer <token>",
        )
    return parts[1].strip()


def resolve_principal_user_id(authorization: Optional[str]) -> str:
    """
    驗證 Supabase JWT 並回傳 principal user_id 字串。
    任何失敗（缺／格式錯／無效／過期／無 principal id）→ 401，
    不回傳或記錄 token、user id、email 或原始例外。
    """
    token = extract_bearer(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="無效或過期的登入憑證")
    principal_user_id = getattr(user, "id", None)
    if not principal_user_id or not str(principal_user_id).strip():
        raise HTTPException(status_code=401, detail="無效或過期的登入憑證")
    return str(principal_user_id)


async def require_principal(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency：回傳已驗證的 principal user_id（唯讀端點授權來源）。"""
    return resolve_principal_user_id(authorization)
