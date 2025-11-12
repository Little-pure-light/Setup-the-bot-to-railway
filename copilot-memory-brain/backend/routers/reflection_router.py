"""
Reflection Router - 反思處理路由
提供反思查詢功能
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
import logging
import sys
import os

project_root = os.path.join(os.path.dirname(__file__), '../../..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.supabase_handler import get_supabase
from config import config

router = APIRouter()
logger = logging.getLogger("reflection_router")

supabase = get_supabase()

@router.get("/reflection/latest")
async def get_latest_reflection(conversation_id: Optional[str] = None):
    """
    取得最新的反思摘要
    
    參數:
        conversation_id: 對話 ID（可選）
    """
    try:
        query = supabase.table(config.SUPABASE_REFLECTIONS_TABLE).select("*")
        
        if conversation_id:
            query = query.eq("conversation_id", conversation_id)
        
        response = query.order("created_at", desc=True).limit(1).execute()
        
        if not response.data:
            return {
                "reflection": None,
                "message": "無反思記錄"
            }
        
        return {
            "reflection": response.data[0],
            "conversation_id": conversation_id
        }
        
    except Exception as e:
        logger.error(f"❌ 取得反思失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reflection/copilot")
async def get_copilot_reflections(limit: int = 10):
    """
    取得所有 Copilot 相關反思
    （透過 copilot_snapshot_id 欄位識別）
    """
    try:
        response = supabase.table(config.SUPABASE_REFLECTIONS_TABLE).select(
            "*"
        ).not_.is_(
            "copilot_snapshot_id", "null"
        ).order("created_at", desc=True).limit(limit).execute()
        
        reflections = response.data if response.data else []
        
        return {
            "count": len(reflections),
            "reflections": reflections
        }
        
    except Exception as e:
        logger.error(f"❌ 取得 Copilot 反思失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reflection/stats")
async def get_reflection_statistics():
    """
    取得反思統計資訊
    """
    try:
        # 總反思數
        total_response = supabase.table(config.SUPABASE_REFLECTIONS_TABLE).select(
            "*", count="exact"
        ).execute()
        
        # Copilot 反思數
        copilot_response = supabase.table(config.SUPABASE_REFLECTIONS_TABLE).select(
            "*", count="exact"
        ).not_.is_("copilot_snapshot_id", "null").execute()
        
        return {
            "total_reflections": total_response.count if total_response.count else 0,
            "copilot_reflections": copilot_response.count if copilot_response.count else 0,
            "shared_database": config.SUPABASE_REFLECTIONS_TABLE
        }
        
    except Exception as e:
        logger.error(f"❌ 取得反思統計失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))
