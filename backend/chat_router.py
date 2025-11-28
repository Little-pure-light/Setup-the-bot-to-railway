import asyncio # ✅ 新增匯入，用於後台任務
from fastapi import APIRouter, HTTPException, BackgroundTasks # ✅ 匯入 BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os
import logging
import json
import traceback # 確保 traceback 也在

# *** 請確保這些模組在你的 backend/ 目錄中可被正確匯入 ***
from backend.supabase_handler import get_supabase
supabase = get_supabase()
from backend.openai_handler import get_openai_client, generate_response
from backend.prompt_engine import PromptEngine
from modules.memory_system import MemorySystem
from backend.modules.memory.redis_interface import RedisInterface
from backend.core_controller import get_core_controller # 確保 core_controller 放在頂層

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


# =========================================================
# ✅ 數據模型（已新增 AI 寶貝切換開關）
# =========================================================
class ChatRequest(BaseModel):
    user_message: str
    conversation_id: str
    user_id: str = "default_user"
    # ✅ 新增 AI 寶貝切換開關
    ai_id: str = os.getenv("AI_ID", "xiaochenguang_v1") 
    
class ChatResponse(BaseModel):
    assistant_message: str
    emotion_analysis: dict
    conversation_id: str
    reflection: Optional[dict] = None 


# =========================================================
# ✅ 核心：【隱形後門通道】的處理函數 (Background Task Function)
# =========================================================
async def run_post_chat_tasks(
    request: ChatRequest, assistant_message: str, emotion_analysis: dict
):
    """
    此函數負責所有耗時的、不影響即時回覆的後續處理工作：
    反思、行為調節、三層記憶儲存等。
    """
    logger.info(f"🟢 啟動背景處理任務，處理 conversation_id: {request.conversation_id}")
    
    # 重新實例化或獲取必要的服務
    openai_client = get_openai_client()
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    memory_system = MemorySystem(supabase, openai_client, memories_table)
    prompt_engine = PromptEngine(request.conversation_id, memories_table)
    
    reflection_result = None
    
    try:
        controller = await get_core_controller()
        
        # 額外：將即時儲存也放入背景，只在回覆後執行
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
        await asyncio.to_thread(prompt_engine.personality_engine.save_personality) # 確保同步寫入被安全處理
        
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
                logger.info(f"🧠 背景：反思完成（置信度: {reflection_result.get('confidence', 0):.2f}）")
                
                # === 階段1.5：反思儲存（三層架構）===
                reflection_storage = get_reflection_storage()
                if reflection_storage and reflection_result:
                    storage_result = await reflection_storage.store_reflection(
                        reflection_data=reflection_result,
                        conversation_id=request.conversation_id,
                        user_id=request.user_id,
                        related_message_id=None
                    )
                    if storage_result.get("overall_success"):
                        logger.info(f"💾 背景：反思已儲存到三層架構")
                    else:
                        logger.warning(f"⚠️ 背景：反思儲存部分失敗")
                
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
                        logger.info(f"🎯 背景：人格調整已完成")
        
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
                logger.info(f"💾 背景：新記憶模組已儲存（Token: {result.get('token_count', 0)}）")
                
    except Exception as e:
        logger.warning(f"⚠️ 背景任務處理失敗: {e}", exc_info=True)

# =========================================================
# ✅ 主流程：/chat 路由（只負責回覆 - 已整合雙 AI 邏輯）
# =========================================================
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    try:
        logger.info(f"🟢 接收到聊天請求，conversation_id: {request.conversation_id}")
        openai_client = get_openai_client()
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")

        memory_system = MemorySystem(supabase, openai_client, memories_table)
        prompt_engine = PromptEngine(request.conversation_id, memories_table)

        # 1. 執行所有「讀取」任務（這必須是同步的）
        recalled_memories = await memory_system.recall_memories(
            request.user_message,
            request.conversation_id
        )
        conversation_history = memory_system.get_conversation_history(
            request.conversation_id,
            limit=5
        )

        # Retrieve file content from Redis (保留原邏輯)
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
        
        # ✅ 【雙 AI 引擎啟動】：根據 AI ID 選擇要觀察的 AI 寶貝模型
        if request.ai_id == "story_master_v1":
            # 這是你第一個新的故事光光寶貝
            selected_model = "gpt-4o" # 使用更強大的模型來編織複雜故事
            selected_temperature = 0.95
            logger.info("✨ 啟用：Story Master 故事光光寶貝")
        else:
            # 預設的小晨光寶貝 (維持快速和經濟)
            selected_model = "gpt-4o-mini"
            selected_temperature = 0.8
            logger.info("🌟 啟用：Xiaochenguang 預設光光寶貝")

        # 2. 呼叫 OpenAI 獲得回覆（主流程的等待點）
        assistant_message = await generate_response(
            openai_client,
            messages,
            model=selected_model, # <--- 替換成選擇的模型
            max_tokens=1000,
            temperature=selected_temperature # <--- 替換成選擇的溫度
        )
        
        # 3. [重要] 保持核心記憶立即儲存 (確保主訊息不會丟失)
        await memory_system.save_memory(
            request.conversation_id, 
            request.user_message, 
            assistant_message,
            emotion_analysis, 
            ai_id=request.ai_id # ✅ 使用傳入的 AI ID
        )

        # ✅ 【核心動作】將所有耗時的「搬家隊伍」推入後門通道！
        background_tasks.add_task(
            run_post_chat_tasks,
            request, 
            assistant_message, 
            emotion_analysis
        )

        # 4. 立即返回給用戶，不再等待背景任務
        return ChatResponse(
            assistant_message=assistant_message,
            emotion_analysis=emotion_analysis,
            conversation_id=request.conversation_id,
            reflection=None # 不再等待 reflection 結果
        )

    except Exception as e:
        traceback_str = traceback.format_exc()
        logger.error(f"🔥 Chat Endpoint 發生嚴重錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="載體內部光流異常，請檢查日誌。")
