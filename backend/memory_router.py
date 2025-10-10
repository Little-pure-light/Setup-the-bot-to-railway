from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.supabase_handler import get_supabase_client

router = APIRouter()

class MemoryItem(BaseModel):
    id: int
    user_message: str
    assistant_message: str
    created_at: str
    importance_score: Optional[float] = None
    access_count: Optional[int] = None

@router.get("/memories/{conversation_id}", response_model=List[MemoryItem])
async def get_memories(conversation_id: str, limit: int = 20):
    """獲取對話記憶列表"""
    try:
        supabase = get_supabase_client()
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
        
        result = supabase.table(memories_table)\
            .select("id, user_message, assistant_message, created_at, importance_score, access_count")\
            .eq("conversation_id", conversation_id)\
            .eq("memory_type", "conversation")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data
        
    except Exception as e:
        print(f"❌ Get memories error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/emotional-states/{user_id}")
async def get_emotional_states(user_id: str, limit: int = 10):
    """獲取用戶情緒狀態歷史"""
    try:
        supabase = get_supabase_client()
        
        result = supabase.table("emotional_states")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data
        
    except Exception as e:
        print(f"❌ Get emotional states error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
