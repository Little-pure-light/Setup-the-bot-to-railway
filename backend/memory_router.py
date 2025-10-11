from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
from backend.utils.supabase_client import supabase
from backend.supabase_handler import supabase



router = APIRouter()
logger = logging.getLogger("memory_router")

class MemoryItem(BaseModel):
    id: int
    user_message: str
    assistant_message: str
    created_at: str
    importance_score: Optional[float] = None
    access_count: Optional[int] = None

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

@router.get("/emotional-states/{user_id}")
async def get_emotional_states(user_id: str, limit: int = 10):
    try:
        logger.info(f"🔍 查詢情緒：user_id={user_id}, limit={limit}")
        result = supabase.table("emotional_states")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()

        logger.info("✅ 情緒查詢成功")
        return result.data

    except Exception as e:
        logger.exception("❌ 讀取情緒失敗")
        raise HTTPException(status_code=500, detail=str(e))


