from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
import traceback

from backend.supabase_handler import get_supabase
from backend.openai_handler import get_openai_client
from modules.memory_system import MemorySystem
from backend.modules.reflection_storage import ReflectionStorage
from backend.redis_interface import RedisInterface
from backend.modules.pinecone_handler import PineconeHandler

supabase = get_supabase()
router = APIRouter()
logger = logging.getLogger("memory_router")


def get_memory_system() -> MemorySystem:
    openai_client = get_openai_client()
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    return MemorySystem(supabase, openai_client, memories_table)


def get_reflection_storage() -> ReflectionStorage:
    try:
        return ReflectionStorage(
            redis_interface=RedisInterface(),
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
