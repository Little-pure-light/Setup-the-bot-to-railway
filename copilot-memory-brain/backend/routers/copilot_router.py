"""
Copilot Router - 主要 Copilot 互動路由
處理前端的 Ask Copilot 請求
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import uuid
from datetime import datetime
import sys
import os

# 添加路徑以 import 主專案模組
project_root = os.path.join(os.path.dirname(__file__), '../../..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.modules.memory.redis_interface import RedisInterface
from backend.supabase_handler import get_supabase
from config import config
from modules.copilot_memory import CopilotMemoryIntegration

router = APIRouter()
logger = logging.getLogger("copilot_router")

# 初始化服務
redis_interface = RedisInterface()
supabase = get_supabase()
copilot_memory = CopilotMemoryIntegration(redis_interface, supabase)

class AskCopilotRequest(BaseModel):
    prompt: str
    conversation_id: str
    user_id: str = "default_user"
    file_name: Optional[str] = None
    file_context: Optional[str] = None

class AskCopilotResponse(BaseModel):
    session_id: str
    status: str
    message: str
    copilot_reply: Optional[str] = None
    memory_summary: Optional[dict] = None
    reflection: Optional[dict] = None

@router.post("/ask_copilot", response_model=AskCopilotResponse)
async def ask_copilot(request: AskCopilotRequest):
    """
    接收前端請求，整合記憶後模擬 Copilot 回覆
    
    流程：
    1. 生成 session_id
    2. 從共用記憶系統讀取最近 5 筆記憶
    3. 讀取人格特質
    4. 組合 prompt（目前模擬 Copilot 回覆）
    5. 寫入記憶到 xiaochenguang_memories
    6. 生成反思並寫入 xiaochenguang_reflections
    7. 返回結果給前端
    """
    
    try:
        # 1. 生成 session_id
        session_id = f"copilot_{uuid.uuid4().hex[:12]}"
        logger.info(f"🟢 收到 Copilot 請求 | session_id: {session_id}")
        
        # 2. 從共用記憶系統讀取最近記憶
        recent_memories = await copilot_memory.get_recent_memories(
            request.conversation_id,
            limit=config.RECENT_MEMORIES_LIMIT
        )
        
        logger.info(f"🧠 讀取到 {len(recent_memories)} 筆相關記憶")
        
        # 3. 讀取人格特質
        personality = await copilot_memory.get_personality_traits()
        logger.info(f"🌈 讀取人格特質: {personality.get('trait', 'default')}")
        
        # 4. 組合完整 prompt
        enhanced_prompt = copilot_memory.build_enhanced_prompt(
            user_prompt=request.prompt,
            recent_memories=recent_memories,
            personality=personality,
            file_name=request.file_name,
            file_context=request.file_context
        )
        
        # 5. 模擬 Copilot 回覆（未來接 VS Code Copilot API）
        # TODO: 整合真正的 Copilot API
        copilot_reply = await copilot_memory.simulate_copilot_response(enhanced_prompt)
        
        logger.info(f"🤖 Copilot 回覆已生成: {copilot_reply[:100]}...")
        
        # 6. 寫入記憶到共用資料庫
        memory_id = await copilot_memory.save_copilot_memory(
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            session_id=session_id,
            user_prompt=request.prompt,
            copilot_reply=copilot_reply,
            file_name=request.file_name
        )
        
        logger.info(f"💾 記憶已儲存 | memory_id: {memory_id}")
        
        # 7. 生成反思並儲存
        reflection = await copilot_memory.generate_and_save_reflection(
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            session_id=session_id,
            user_prompt=request.prompt,
            copilot_reply=copilot_reply,
            memory_id=memory_id
        )
        
        logger.info(f"💭 反思已生成並儲存")
        
        # 8. 記錄 session 狀態到 Redis
        await copilot_memory.save_session_status(
            session_id=session_id,
            status="completed",
            file_name=request.file_name
        )
        
        return AskCopilotResponse(
            session_id=session_id,
            status="completed",
            message="Copilot 回覆已生成並儲存",
            copilot_reply=copilot_reply,
            memory_summary={
                "recent_count": len(recent_memories),
                "personality": personality.get("trait", "default"),
                "memory_id": memory_id
            },
            reflection={
                "content": reflection.get("content", ""),
                "confidence": reflection.get("confidence", 0.0)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Copilot 處理失敗: {e}")
        raise HTTPException(status_code=500, detail=f"Copilot 處理失敗: {str(e)}")

@router.get("/session/{session_id}")
async def get_session_status(session_id: str):
    """查詢 session 狀態"""
    try:
        status = await copilot_memory.get_session_status(session_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Session 不存在")
        
        return {
            "session_id": session_id,
            "status": status.get("status", "unknown"),
            "file_name": status.get("file_name"),
            "created_at": status.get("created_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 查詢 session 失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))
