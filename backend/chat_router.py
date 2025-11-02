from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import logging
import json
from backend.supabase_handler import get_supabase
supabase = get_supabase()
from backend.openai_handler import get_openai_client, generate_response
from backend.prompt_engine import PromptEngine
from modules.memory_system import MemorySystem
from backend.modules.memory.redis_interface import RedisInterface

router = APIRouter()
logger = logging.getLogger("chat_router")
redis_interface = RedisInterface()

_new_memory_core = None
_reflection_storage = None

def get_new_memory_core():
    """獲取新記憶模組核心（延遲初始化）"""
    global _new_memory_core
    if _new_memory_core is None:
        try:
            from backend.modules.memory.core import MemoryCore
            _new_memory_core = MemoryCore()
            logger.info("✅ 新記憶模組已啟用")
        except Exception as e:
            logger.warning(f"⚠️ 新記憶模組初始化失敗: {e}")
            _new_memory_core = None
    return _new_memory_core

def get_reflection_storage():
    """獲取反思儲存服務（延遲初始化）"""
    global _reflection_storage
    if _reflection_storage is None:
        try:
            from backend.modules.reflection_storage import ReflectionStorage
            from backend.modules.memory.redis_interface import RedisInterface
            from backend.modules.pinecone_handler import PineconeHandler
            
            redis_interface = RedisInterface()
            pinecone_handler = PineconeHandler()
            
            _reflection_storage = ReflectionStorage(
                redis_interface=redis_interface,
                supabase_client=supabase,
                pinecone_handler=pinecone_handler
            )
            logger.info("✅ 反思儲存服務已啟用")
        except Exception as e:
            logger.warning(f"⚠️ 反思儲存服務初始化失敗: {e}")
            _reflection_storage = None
    return _reflection_storage

class ChatRequest(BaseModel):
    user_message: str
    conversation_id: str
    user_id: str = "default_user"

class ChatResponse(BaseModel):
    assistant_message: str
    emotion_analysis: dict
    conversation_id: str
    reflection: Optional[dict] = None

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        logger.info(f"🟢 接收到聊天請求，conversation_id: {request.conversation_id}")
        openai_client = get_openai_client()
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")

        memory_system = MemorySystem(supabase, openai_client, memories_table)
        prompt_engine = PromptEngine(request.conversation_id, memories_table)

        recalled_memories = await memory_system.recall_memories(
            request.user_message,
            request.conversation_id
        )
        logger.debug(f"🧠 回憶資料：{recalled_memories}")

        conversation_history = memory_system.get_conversation_history(
            request.conversation_id,
            limit=5
        )
        logger.debug(f"📜 對話歷史：{conversation_history}")

        # Retrieve file content from Redis
        file_content = ""
        try:
            keys = redis_interface.redis.keys(f"upload:{request.conversation_id}:*")
            if keys:
                latest_key = keys[-1]
                file_data_json = redis_interface.redis.get(latest_key)
                if file_data_json:
                    file_data = json.loads(file_data_json)
                    file_content = file_data.get("content", "")
                    logger.info(f"📄 成功從 Redis 檢索檔案內容: {latest_key}")
        except Exception as e:
            logger.warning(f"⚠️ 從 Redis 檢索檔案內容失敗: {e}")

        messages, emotion_analysis = await prompt_engine.build_prompt(
            request.user_message,
            recalled_memories,
            conversation_history,
            file_content
        )

        assistant_message = await generate_response(
            openai_client,
            messages,
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.8
        )

        await memory_system.save_memory(
            request.conversation_id,
            request.user_message,
            assistant_message,
            emotion_analysis,
            ai_id=os.getenv("AI_ID", "xiaochenguang_v1")
        )

        await memory_system.save_emotional_state(
            request.user_id,
            emotion_analysis,
            context=request.user_message
        )

        prompt_engine.personality_engine.learn_from_interaction(
            request.user_message,
            assistant_message,
            emotion_analysis
        )
        prompt_engine.personality_engine.save_personality()
        
        reflection_result = None
        behavior_adjustment = None
        
        try:
            from backend.core_controller import get_core_controller
            controller = await get_core_controller()
            
            # === 階段1：反思分析 ===
            reflection_module = await controller.get_module("reflection")
            if reflection_module:
                reflection_response = await reflection_module.process({
                    "user_message": request.user_message,
                    "assistant_message": assistant_message,
                    "emotion_analysis": emotion_analysis
                })
                
                if reflection_response.get("success"):
                    reflection_result = reflection_response.get("reflection")
                    logger.info(f"🧠 反思完成（置信度: {reflection_result.get('confidence', 0):.2f}）")
                    
                    # === 階段1.5：反思儲存（三層架構：Redis + Supabase + Pinecone）===
                    reflection_storage = get_reflection_storage()
                    if reflection_storage and reflection_result:
                        storage_result = await reflection_storage.store_reflection(
                            reflection_data=reflection_result,
                            conversation_id=request.conversation_id,
                            user_id=request.user_id,
                            related_message_id=None
                        )
                        
                        if storage_result.get("overall_success"):
                            logger.info(f"💾 反思已儲存到三層架構 (ID: {storage_result.get('reflection_id')})")
                            logger.info(f"   - Redis: {'✅' if storage_result.get('redis_success') else '❌'}")
                            logger.info(f"   - Supabase: {'✅' if storage_result.get('supabase_success') else '❌'}")
                            logger.info(f"   - Pinecone: {'✅' if storage_result.get('pinecone_success') else '❌'}")
                        else:
                            logger.warning(f"⚠️ 反思儲存部分失敗")
                    
                    # === 階段2：行為調節（基於反思結果）===
                    behavior_module = await controller.get_module("behavior")
                    if behavior_module and reflection_result:
                        behavior_response = await behavior_module.process({
                            "reflection": reflection_result,
                            "emotion_analysis": emotion_analysis,
                            "conversation_context": {
                                "user_message": request.user_message,
                                "assistant_message": assistant_message
                            }
                        })
                        
                        if behavior_response.get("success"):
                            behavior_adjustment = behavior_response
                            personality_vector = behavior_response.get("personality_vector", {})
                            adjustments = behavior_response.get("adjustments", {})
                            
                            if adjustments:
                                logger.info(f"🎯 人格調整: {adjustments}")
                                logger.info(f"📊 新人格向量: {personality_vector}")
            
            # === 階段3：記憶儲存（含反思與行為調整）===
            new_memory = get_new_memory_core()
            if new_memory:
                result = new_memory.store_conversation(
                    conversation_id=request.conversation_id,
                    user_id=request.user_id,
                    user_msg=request.user_message,
                    assistant_msg=assistant_message,
                    reflection=reflection_result
                )
                if result.get("success"):
                    logger.info(f"💾 新記憶模組已儲存（Token: {result.get('token_count', 0)}）")
        except Exception as e:
            logger.warning(f"⚠️ 新記憶/反思/行為調節模組處理失敗（不影響主流程）: {e}")

        return ChatResponse(
            assistant_message=assistant_message,
            emotion_analysis=emotion_analysis,
            conversation_id=request.conversation_id,
            reflection=reflection_result
        )

    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        print("🔥 Exception occurred:", traceback_str)
        raise HTTPException(status_code=500, detail=traceback_str)
