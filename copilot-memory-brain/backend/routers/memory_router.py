"""
Memory Router - 記憶查詢路由
提供記憶檢索功能
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from backend.modules.memory.redis_interface import RedisInterface
from backend.supabase_handler import get_supabase
from copilot_memory_brain.backend.config import config
from copilot_memory_brain.backend.modules.copilot_memory import CopilotMemoryIntegration

router = APIRouter()
logger = logging.getLogger("memory_router")

# 初始化服務
redis_interface = RedisInterface()
supabase = get_supabase()
copilot_memory = CopilotMemoryIntegration(redis_interface, supabase)

@router.get("/memory/recent")
async def get_recent_memories(
    conversation_id: Optional[str] = None,
    limit: int = 10
):
    """
    取得最近的記憶
    
    參數:
        conversation_id: 對話 ID（可選）
        limit: 返回數量（預設 10）
    """
    try:
        memories = await copilot_memory.get_recent_memories(
            conversation_id=conversation_id,
            limit=limit
        )
        
        return {
            "count": len(memories),
            "memories": memories,
            "conversation_id": conversation_id
        }
        
    except Exception as e:
        logger.error(f"❌ 取得記憶失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/memory/copilot")
async def get_copilot_memories(limit: int = 20):
    """
    取得所有 Copilot 相關記憶
    （platform = vscode）
    """
    try:
        response = supabase.table(config.SUPABASE_MEMORIES_TABLE).select("*").eq(
            "platform", config.COPILOT_PLATFORM
        ).order("created_at", desc=True).limit(limit).execute()
        
        memories = response.data if response.data else []
        
        return {
            "count": len(memories),
            "memories": memories,
            "platform": config.COPILOT_PLATFORM
        }
        
    except Exception as e:
        logger.error(f"❌ 取得 Copilot 記憶失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/memory/stats")
async def get_memory_statistics():
    """
    取得記憶統計資訊
    """
    try:
        # 總記憶數
        total_response = supabase.table(config.SUPABASE_MEMORIES_TABLE).select(
            "*", count="exact"
        ).execute()
        
        # Copilot 記憶數
        copilot_response = supabase.table(config.SUPABASE_MEMORIES_TABLE).select(
            "*", count="exact"
        ).eq("platform", config.COPILOT_PLATFORM).execute()
        
        # 小宸光記憶數
        xiaochenguang_response = supabase.table(config.SUPABASE_MEMORIES_TABLE).select(
            "*", count="exact"
        ).eq("platform", "telegram").execute()
        
        return {
            "total_memories": total_response.count if total_response.count else 0,
            "copilot_memories": copilot_response.count if copilot_response.count else 0,
            "xiaochenguang_memories": xiaochenguang_response.count if xiaochenguang_response.count else 0,
            "shared_database": config.SUPABASE_MEMORIES_TABLE
        }
        
    except Exception as e:
        logger.error(f"❌ 取得統計資訊失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))
