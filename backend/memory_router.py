from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timezone
import os
import re
import logging
import traceback

from backend.supabase_handler import get_supabase
from backend.openai_handler import get_openai_client
from backend.auth_principal import require_principal
from backend.modules.memory_types import MEMORY_TYPES, V1_CONVERSATION_TYPE
from modules.memory_system import MemorySystem
from backend.modules.reflection_storage import ReflectionStorage
from backend.redis_interface import get_shared_redis_interface
from backend.modules.pinecone_handler import PineconeHandler

try:
    from backend.logging_utils import get_request_id
except Exception:  # pragma: no cover - logging_utils 未載入時的保底
    def get_request_id() -> str:
        return ""

supabase = get_supabase()
router = APIRouter()
logger = logging.getLogger("memory_router")


def _memories_table() -> str:
    return os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")


def _current_ai_id() -> str:
    # 與 chat_router／archive 寫入 conversation row 時的 ai_id 一致
    return os.getenv("AI_ID", "xiaochenguang_v1")


# ---------------------------------------------------------------------------
# 唯讀記憶中心（增量1）— owner-scoped 檢視契約
# 重用 Task010-001 owner-scoped 唯讀 API 契約（原分支 feature/task010-001-readonly-
# memory-center，未併入 main），本增量將其收斂為「僅新增」變更：只加入 /memory-center
# 端點與其 JWT principal 依賴，不改動既有 get_memories／recent-history／emotional-states
# 端點行為（既有端點的 hardening 留待後續批次，避免本唯讀增量夾帶行為變更）。
# ---------------------------------------------------------------------------

# 唯讀記憶中心可篩選的 memory_type allowlist。
# 單一權威來源 = 正式 V2 taxonomy（backend/modules/memory_types.py 的 MEMORY_TYPES）
#   + V1 對話列型別（V1_CONVERSATION_TYPE = "conversation"）
#   + 明確記錄、且經 source 證實「確實以 memory_type 持久化寫入 Supabase」的 legacy 型別：
#     conversation_summary -> backend/history_router.py（寫入 Supabase memory row）
#     personality          -> modules/personality_engine.py（寫入 Supabase memory row）
# 註：不含 "graph"——它僅為 retrieval_engine 召回/graph expansion 的回應標籤，
#     並無 memory_type=graph 的持久化 insert/update。
LEGACY_FILTERABLE_MEMORY_TYPES = ("conversation_summary", "personality")
MEMORY_TYPE_ALLOWLIST = tuple(
    dict.fromkeys(MEMORY_TYPES + (V1_CONVERSATION_TYPE,) + LEGACY_FILTERABLE_MEMORY_TYPES)
)

# 回傳欄位 allowlist：禁止 embedding、document 內部 metadata、owner id、ai id、file/platform、email、token。
MEMORY_CENTER_SELECT = (
    "id, memory_type, created_at, conversation_id, "
    "user_message, assistant_message, importance_score, access_count"
)

# 搜尋輸入邊界：長度上限 + 安全 in-Python 過濾（不把 raw query 拼進 SQL／PostgREST expression）。
SEARCH_MAX_LEN = 100
SEARCH_SCAN_CAP = 200

# created_from/to 驗證：先用「明確 grammar」限定支援格式，再做語意（真實日期）驗證。
# 明確契約（deterministic；不依賴 datetime.fromisoformat 的隱含寬鬆行為）：
#   - 純日期： YYYY-MM-DD
#   - datetime： YYYY-MM-DDTHH:MM[:SS][.fff...]  後可接 Z 或數字 offset ±HH:MM
#   - 分隔符固定為大寫 "T"；不接受空白分隔、不接受 compact（YYYYMMDD）等變體。
#   - 無時區的 datetime 一律視為 UTC（供 deterministic 比較）。
# 供給契約：只有 None 代表「未提供」；空字串／純空白 → 422（視為使用者提供了無效值）。
# grammar 不含逗號/括號/引號/百分號，對 PostgREST 過濾值安全；語意錯（不存在日期）在查 DB 前 422。
_ISO_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$"
)


def _parse_iso_or_422(value: Optional[str]):
    if value is None:
        return None  # 未提供此 filter
    v = value.strip()
    if not v:
        # 使用者提供了空字串／純空白：視為無效輸入，不 silently 當未提供。
        raise HTTPException(status_code=422, detail="日期不可為空")
    if _ISO_DATE_ONLY_RE.match(v):
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise HTTPException(status_code=422, detail="日期格式不合法")
        return v, datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if _ISO_DATETIME_RE.match(v):
        candidate = v[:-1] + "+00:00" if v.endswith("Z") else v
        try:
            dt = datetime.fromisoformat(candidate)
        except ValueError:
            raise HTTPException(status_code=422, detail="日期格式不合法")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return v, dt
    # 不符合明確 grammar（compact、空白分隔、任意分隔符、垃圾等）→ 422
    raise HTTPException(status_code=422, detail="日期格式不合法")


def get_memory_system() -> MemorySystem:
    openai_client = get_openai_client()
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    return MemorySystem(supabase, openai_client, memories_table)


def get_reflection_storage() -> ReflectionStorage:
    try:
        return ReflectionStorage(
            redis_interface=get_shared_redis_interface(),
            supabase_client=supabase,
            pinecone_handler=PineconeHandler()
        )
    except Exception as e:
        logger.error(f"⚠️ ReflectionStorage 初始化失敗: {e}")
        raise HTTPException(status_code=500, detail="後端服務初始化錯誤: ReflectionStorage")


class MemoryItem(BaseModel):
    id: int
    user_message: str
    assistant_message: str
    created_at: str
    importance_score: Optional[float] = None
    access_count: Optional[int] = None


class SaveMemoryRequest(BaseModel):
    memory_type: str = "code"
    code_context: str
    summary: str
    source: str = "vs_code"
    ai_id: str = "copilot_brain"
    user_id: str = "default_user"


class SearchMemoryRequest(BaseModel):
    query: str
    user_id: str = "default_user"
    conversation_id: Optional[str] = None


class MemoryCenterItem(BaseModel):
    id: int
    memory_type: Optional[str] = None
    created_at: Optional[str] = None
    conversation_id: Optional[str] = None
    user_message: Optional[str] = None
    assistant_message: Optional[str] = None
    importance_score: Optional[float] = None
    access_count: Optional[int] = None


class MemoryCenterResponse(BaseModel):
    items: List[MemoryCenterItem]
    limit: int
    offset: int
    count: int
    # 誠實揭露：使用 q 搜尋時，範圍為「最近 N 筆 owner-scoped rows 的 deterministic 過濾」。
    search_scope: Optional[str] = None


@router.get("/memory-center", response_model=MemoryCenterResponse)
async def memory_center(
    principal: str = Depends(require_principal),
    memory_type: Optional[str] = Query(default=None),
    created_from: Optional[str] = Query(default=None),
    created_to: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, max_length=SEARCH_MAX_LEN),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=1000),
):
    """登入者唯讀記憶中心：owner + 目前 ai_id 綁定的列表／篩選／安全搜尋。

    - 所有 query 先套 exact user_id + ai_id，filter 只能再縮小、不放寬 owner scope。
    - memory_type 必須在 allowlist；未知 → 422。
    - created_from/to 僅允許 ISO 安全字元；非法 → 422。
    - 搜尋 q 不拼入 SQL／PostgREST：抓有界 owner-scoped rows 後 deterministic in-Python 子字串過濾。
    - deterministic 分頁（created_at desc, id desc）與固定 sort；不接受 client 送任意欄名／SQL。
    - 回傳欄位 allowlist；無 embedding／owner id／ai id／metadata／token。
    """
    rid = get_request_id() or ""
    ai_id = _current_ai_id()

    if memory_type is not None and memory_type not in MEMORY_TYPE_ALLOWLIST:
        raise HTTPException(status_code=422, detail="不支援的 memory_type")

    cf_parsed = _parse_iso_or_422(created_from)
    ct_parsed = _parse_iso_or_422(created_to)
    if cf_parsed and ct_parsed and cf_parsed[1] > ct_parsed[1]:
        raise HTTPException(status_code=422, detail="created_from 不可晚於 created_to")
    cf = cf_parsed[0] if cf_parsed else None
    ct = ct_parsed[0] if ct_parsed else None

    needle = None
    if q is not None:
        q_stripped = q.strip()
        if q_stripped:
            needle = q_stripped.casefold()

    def _scoped():
        b = (
            supabase.table(_memories_table())
            .select(MEMORY_CENTER_SELECT)
            .eq("user_id", principal)
            .eq("ai_id", ai_id)
        )
        if memory_type is not None:
            b = b.eq("memory_type", memory_type)
        if cf is not None:
            b = b.gte("created_at", cf)
        if ct is not None:
            b = b.lte("created_at", ct)
        return b.order("created_at", desc=True).order("id", desc=True)

    try:
        if needle is None:
            result = _scoped().range(offset, offset + limit - 1).execute()
            items = result.data or []
            scope = None
        else:
            # 有界掃描 + deterministic 過濾；raw query 永不進入 SQL／PostgREST。
            result = _scoped().limit(SEARCH_SCAN_CAP).execute()
            rows = result.data or []
            matched = [
                r for r in rows
                if needle in (
                    ((r.get("user_message") or "") + "\n" + (r.get("assistant_message") or "")).casefold()
                )
            ]
            items = matched[offset: offset + limit]
            scope = f"recent_{SEARCH_SCAN_CAP}_owner_rows"
    except HTTPException:
        raise
    except Exception:
        logger.error("memory_center read_error request_id=%s", rid)
        raise HTTPException(status_code=502, detail="記憶服務暫時無法使用，請稍後再試")

    logger.info("memory_center ok request_id=%s count=%d", rid, len(items))
    return MemoryCenterResponse(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        search_scope=scope,
    )


@router.get("/memories/{conversation_id}", response_model=List[MemoryItem])
async def get_memories(conversation_id: str, limit: int = 20):
    try:
        logger.info(f"🔍 查詢記憶：conversation_id={conversation_id}, limit={limit}")
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")

        result = supabase.table(memories_table)\
            .select("id, user_message, assistant_message, created_at, importance_score, access_count")\
            .eq("conversation_id", conversation_id)\
            .eq("memory_type", "conversation")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()

        logger.info("✅ 記憶查詢成功")
        return result.data

    except Exception as e:
        logger.exception("❌ 讀取記憶失敗")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-history/{user_id}")
async def get_recent_history(user_id: str, limit: int = 30):
    """根據 user_id 取得最近對話歷史（跨裝置載入）"""
    try:
        logger.info(f"🔍 查詢最近歷史：user_id={user_id}, limit={limit}")
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")

        result = supabase.table(memories_table)\
            .select("user_message, assistant_message, created_at, conversation_id")\
            .eq("user_id", user_id)\
            .eq("memory_type", "conversation")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()

        if not result.data:
            return {"messages": [], "conversation_id": None}

        rows = list(reversed(result.data))
        messages = []
        for row in rows:
            ts = row.get("created_at", "")[:19].replace("T", " ")
            if row.get("user_message"):
                messages.append({
                    "type": "user",
                    "content": row["user_message"],
                    "timestamp": ts,
                    "streaming": False
                })
            if row.get("assistant_message"):
                messages.append({
                    "type": "assistant",
                    "content": row["assistant_message"],
                    "timestamp": ts,
                    "streaming": False
                })

        latest_conv_id = result.data[0].get("conversation_id") if result.data else None
        logger.info(f"✅ 最近歷史查詢成功：{len(messages)} 則訊息")
        return {"messages": messages, "conversation_id": latest_conv_id}

    except Exception as e:
        logger.exception("❌ 讀取最近歷史失敗")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emotional-states/{user_id}")
async def get_emotional_states(user_id: str, limit: int = 10):
    try:
        logger.info(f"🔍 查詢情緒：user_id={user_id}, limit={limit}")
        result = supabase.table("emotional_states")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()

        logger.info("✅ 情緒查詢成功")
        return result.data
    except Exception as e:
        logger.exception("❌ 讀取情緒失敗")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save_memory")
async def save_memory(
    request: SaveMemoryRequest,
    memory_system: MemorySystem = Depends(get_memory_system),
):
    """儲存程式碼／外部記憶片段（統一走 MemorySystem）"""
    logger.info(f"💾 接收到記憶請求: {request.summary[:80]}")
    try:
        await memory_system.save_memory(
            conversation_id=f"external_{request.user_id}",
            user_input=request.code_context,
            bot_response=request.summary,
            emotion_analysis={"dominant_emotion": "neutral", "intensity": 0.5},
            ai_id=request.ai_id,
            user_id=request.user_id,
        )
        return {"success": True, "message": "記憶已儲存"}
    except Exception as e:
        logger.error(f"❌ 儲存記憶路由錯誤: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="無法儲存記憶")


@router.post("/memory/search")
async def search_memory(
    request: SearchMemoryRequest,
    memory_system: MemorySystem = Depends(get_memory_system),
):
    """向量記憶檢索"""
    logger.info(f"🔍 接收到記憶檢索請求: {request.query}")
    try:
        conversation_id = request.conversation_id or f"external_{request.user_id}"
        recalled = await memory_system.recall_memories(
            user_message=request.query,
            conversation_id=conversation_id,
            user_id=request.user_id,
        )
        return {"success": True, "results": recalled}
    except Exception as e:
        logger.error(f"❌ 記憶檢索路由錯誤: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="無法檢索記憶")


@router.post("/memory/reflection")
async def trigger_reflection(
    reflection_storage: ReflectionStorage = Depends(get_reflection_storage),
):
    """主動觸發反思流程（預留端點）"""
    logger.info("🧠 接收到主動反思觸發請求...")
    try:
        return {
            "success": True,
            "message": "反思觸發請求已接收（對話後會自動在背景執行）",
        }
    except Exception as e:
        logger.error(f"❌ 反思觸發路由錯誤: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="無法觸發反思")
