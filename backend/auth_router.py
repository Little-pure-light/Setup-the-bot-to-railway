"""
Supabase Auth 相關 API

- 驗證 JWT、回傳目前使用者
- 登入後載入個人記憶摘要與人格（跨裝置同步）
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import logging
import json

from backend.supabase_handler import get_supabase, get_user_from_token

router = APIRouter()
logger = logging.getLogger("auth_router")


class AuthUserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    created_at: Optional[str] = None


class UserSyncResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    conversation_id: Optional[str] = None
    message_count: int = 0
    messages: list = []
    personality: Dict[str, Any] = {}


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Authorization 格式錯誤，請使用 Bearer <token>")
    return parts[1].strip()


@router.get("/auth/me", response_model=AuthUserResponse)
async def auth_me(authorization: Optional[str] = Header(default=None)):
    """驗證 Supabase JWT，回傳目前登入使用者。"""
    token = _extract_bearer(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="無效或過期的登入憑證")

    return AuthUserResponse(
        id=user.id,
        email=getattr(user, "email", None),
        created_at=str(getattr(user, "created_at", "") or "") or None,
    )


@router.get("/auth/sync", response_model=UserSyncResponse)
async def auth_sync(
    authorization: Optional[str] = Header(default=None),
    limit: int = 30,
):
    """
    登入後一次同步：
    - 驗證 JWT
    - 載入該 user_id 的最近對話記憶
    - 載入人格（優先 user_id，其次最近 conversation_id）
    """
    token = _extract_bearer(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="無效或過期的登入憑證")

    user_id = user.id
    email = getattr(user, "email", None)
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    supabase = get_supabase()

    messages = []
    conversation_id = None
    message_count = 0

    try:
        result = (
            supabase.table(memories_table)
            .select("user_message, assistant_message, created_at, conversation_id")
            .eq("user_id", user_id)
            .eq("memory_type", "conversation")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        if result.data:
            message_count = len(result.data)
            conversation_id = result.data[0].get("conversation_id")
            rows = list(reversed(result.data))
            for row in rows:
                ts = (row.get("created_at") or "")[:19].replace("T", " ")
                if row.get("user_message"):
                    messages.append({
                        "type": "user",
                        "content": row["user_message"],
                        "timestamp": ts,
                        "streaming": False,
                    })
                if row.get("assistant_message"):
                    messages.append({
                        "type": "assistant",
                        "content": row["assistant_message"],
                        "timestamp": ts,
                        "streaming": False,
                    })
    except Exception as e:
        logger.warning(f"⚠️ 同步記憶失敗（繼續人格載入）: {e}")

    personality: Dict[str, Any] = {}
    try:
        # 優先以 user_id 載入人格
        pers = (
            supabase.table(memories_table)
            .select("document_content, conversation_id")
            .eq("user_id", user_id)
            .eq("memory_type", "personality")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not pers.data and conversation_id:
            pers = (
                supabase.table(memories_table)
                .select("document_content, conversation_id")
                .eq("conversation_id", conversation_id)
                .eq("memory_type", "personality")
                .limit(1)
                .execute()
            )
        if pers.data and pers.data[0].get("document_content"):
            raw = pers.data[0]["document_content"]
            personality = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.warning(f"⚠️ 同步人格失敗: {e}")

    # 嘗試 user_preferences 補充
    try:
        pref = (
            supabase.table("user_preferences")
            .select("personality_profile")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not pref.data and conversation_id:
            pref = (
                supabase.table("user_preferences")
                .select("personality_profile")
                .eq("conversation_id", conversation_id)
                .limit(1)
                .execute()
            )
        if pref.data and pref.data[0].get("personality_profile"):
            profile_raw = pref.data[0]["personality_profile"]
            profile_data = json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
            personality.setdefault("db_traits", profile_data)
    except Exception:
        pass

    logger.info(
        f"✅ 使用者同步完成 user={user_id[:8]}... msgs={message_count} "
        f"conv={str(conversation_id)[:8] if conversation_id else 'none'}..."
    )
    return UserSyncResponse(
        user_id=user_id,
        email=email,
        conversation_id=conversation_id,
        message_count=message_count,
        messages=messages,
        personality=personality,
    )


@router.get("/personality/{user_id}")
async def get_personality(user_id: str):
    """依 user_id 載入人格摘要（跨裝置）。"""
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    supabase = get_supabase()
    try:
        result = (
            supabase.table(memories_table)
            .select("document_content, created_at, conversation_id")
            .eq("user_id", user_id)
            .eq("memory_type", "personality")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return {
                "user_id": user_id,
                "personality": None,
                "message": "尚無已儲存的人格資料",
            }
        raw = result.data[0].get("document_content")
        data = json.loads(raw) if isinstance(raw, str) else raw
        return {
            "user_id": user_id,
            "conversation_id": result.data[0].get("conversation_id"),
            "created_at": result.data[0].get("created_at"),
            "personality": data,
        }
    except Exception as e:
        logger.exception("❌ 讀取人格失敗")
        raise HTTPException(status_code=500, detail=str(e))
