"""
對話封存端點（私有 · owner-scoped）

Task008-001：
- 只允許「已登入的 owner」封存自己的對話。
- 以 Supabase JWT 驗證取得 principal user id；request body 的 user_id 不得作為授權來源。
- 只查 conversation_id + principal user_id + 目前 ai_id + memory_type=conversation。
- 不呼叫 IPFS／Pinata、不掃 Redis 附件、不寫 conversation_archive；不做任何公開上傳。
- 正常聊天的 conversation row 已持久保存於 owner-scoped 記憶，驗證存在即回傳誠實的
  private_existing_memory 結果，不複製全文、不產生 CID、不上傳到公開 IPFS。
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
import os

from backend.supabase_handler import get_supabase, get_user_from_token

try:
    from backend.logging_utils import get_request_id
except Exception:  # pragma: no cover - logging_utils 未載入時的保底
    def get_request_id() -> str:
        return ""

router = APIRouter()
logger = logging.getLogger("archive_conversation")


def _memories_table() -> str:
    return os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")


def _current_ai_id() -> str:
    # 與 chat_router 寫入 conversation row 時的 ai_id 一致
    return os.getenv("AI_ID", "xiaochenguang_v1")


def _extract_bearer(authorization: Optional[str]) -> str:
    """從 Authorization header 取出 Bearer token；缺少或格式錯誤一律 401。"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=401,
            detail="Authorization 格式錯誤，請使用 Bearer <token>",
        )
    return parts[1].strip()


class ArchiveRequest(BaseModel):
    conversation_id: str
    # 相容欄位：舊前端仍可能送 user_id，但不得作為授權來源。
    user_id: Optional[str] = None
    # 相容欄位：附件在本版不另外封存（owner key 契約未完成，fail-closed）。
    include_attachments: bool = True


class ArchiveResponse(BaseModel):
    success: bool
    mode: str
    message_count: int = 0
    attachments_archived: bool = False
    # 向後相容的舊欄位：私有封存不產生公開 CID／gateway，固定為 null。
    ipfs_cid: Optional[str] = None
    gateway_url: Optional[str] = None
    archive_id: Optional[str] = None
    message: str
    archived_at: str


@router.post("/archive_conversation", response_model=ArchiveResponse)
async def archive_conversation(
    request: ArchiveRequest,
    authorization: Optional[str] = Header(default=None),
):
    """私有 owner-scoped 封存：驗證登入者確實擁有此對話，回傳誠實的私人保留結果。"""
    rid = get_request_id() or ""

    # 1) 驗證 JWT，取得 principal（缺／格式錯／無效或過期 → 401）
    token = _extract_bearer(authorization)
    user = get_user_from_token(token)
    if not user:
        logger.warning("archive unauthorized request_id=%s", rid)
        raise HTTPException(status_code=401, detail="無效或過期的登入憑證")
    principal_user_id = getattr(user, "id", None)
    if not principal_user_id:
        logger.warning("archive unauthorized_no_principal request_id=%s", rid)
        raise HTTPException(status_code=401, detail="無效或過期的登入憑證")

    # 2) body user_id 僅為相容欄位；若與 principal 不符 → 403（不得靜默改用 body owner）
    body_user_id = (request.user_id or "").strip()
    if body_user_id and body_user_id != str(principal_user_id):
        logger.warning("archive forbidden_owner_mismatch request_id=%s", rid)
        raise HTTPException(status_code=403, detail="無權限封存此對話")

    ai_id = _current_ai_id()

    # 3) owner-scoped 查詢：conversation_id + principal user_id + 目前 ai_id + conversation
    #    只取判定所需欄位，不組任何公開全文 payload。
    try:
        result = (
            get_supabase()
            .table(_memories_table())
            .select("id, created_at")
            .eq("conversation_id", request.conversation_id)
            .eq("user_id", str(principal_user_id))
            .eq("ai_id", ai_id)
            .eq("memory_type", "conversation")
            .order("created_at", desc=False)
            .execute()
        )
        rows = result.data or []
    except HTTPException:
        raise
    except Exception:
        # 去敏：不回傳原始錯誤、不宣稱成功
        logger.error("archive supabase_error request_id=%s", rid)
        raise HTTPException(
            status_code=502,
            detail="封存服務暫時無法使用，請稍後再試",
        )

    # 4) 不存在或不屬於此 owner／AI → 一致 404（避免枚舉他人資料存在性）
    if not rows:
        logger.info("archive not_found request_id=%s", rid)
        raise HTTPException(status_code=404, detail="找不到對話或無權限存取")

    # 5) 誠實結果：私人對話已保留於 owner-scoped 記憶；
    #    不複製全文、不產生 CID、不上傳 IPFS、不寫 conversation_archive。
    now = datetime.utcnow().isoformat()
    logger.info("archive ok request_id=%s rows=%d", rid, len(rows))
    return ArchiveResponse(
        success=True,
        mode="private_existing_memory",
        message_count=len(rows),
        attachments_archived=False,
        ipfs_cid=None,
        gateway_url=None,
        archive_id=None,
        message="此對話已安全保留在你的私人記憶中（未公開上傳；附件未另外封存）。",
        archived_at=now,
    )
