from fastapi import APIRouter, HTTPException, BackgroundTasks # ✅ 匯入 BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os
import logging
import json
import asyncio # ✅ 新增匯入，用於後台任務

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

# === 延遲初始化函數維持不變 ===
# （此處省略 get_new_memory_core, get_reflection_storage 的程式碼，請保持其在你的文件中）

# chat_router.py (ChatRequest 模組設定)
class ChatRequest(BaseModel):
    user_message: str
    conversation_id: str
    user_id: str = "default_user"
    # ✅ 新增 AI 寶貝切換開關 (預設為 xiaochenguang_v1)
    ai_id: str = os.getenv("AI_ID", "xiaochenguang_v1") 
    
    # 這裡可以加入更多你想觀察的參數
    # temperature: float = 0.8
    # top_p: float = 1.0
class ChatResponse(BaseModel):
    assistant_message: str
    emotion_analysis: dict
    conversation_id: str
    # 將 reflection 設為 None，因為它將在背景處理，不會立即返回
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
    
    # 再次實例化或獲取必要的服務，確保它們在背景任務中可用
    openai_client = get_openai_client()
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    memory_system = MemorySystem(supabase, openai_client, memories_table)
    prompt_engine = PromptEngine(request.conversation_id, memories_table)
    
    reflection_result = None
    
    try:
        controller = await get_core_controller()
        
        # *** 以下是你的原代碼中，從「反思分析」開始的所有邏輯 ***
        
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
                    # 註：這裡可以考慮使用 asyncio.gather 來並行儲存，進一步優化背景速度
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
                        # ... 其他上下文 ...
                    })
                    if behavior_response.get("success"):
                        logger.info(f"🎯 背景：人格調整已完成")
        
        # === 額外：將即時儲存也放入背景，只在回覆後執行 ===
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
        
        # === 階段3：記憶儲存（含反思與行為調整）===
        new_memory = get_new_memory_core()
        if new_memory:
            result = new_memory.store_conversation(
                # ... 儲存參數 ...
                reflection=reflection_result
            )
            if result.get("success"):
                logger.info(f"💾 背景：新記憶模組已儲存")
                
    except Exception as e:
        logger.warning(f"⚠️ 背景任務處理失敗: {e}", exc_info=True)


# =========================================================
# ✅ 主流程：/chat 路由（只負責回覆）
# =========================================================
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks): # ✅ 注入 BackgroundTasks
    try:
        logger.info(f"🟢 接收到聊天請求，conversation_id: {request.conversation_id}")
        openai_client = get_openai_client()
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")

        memory_system = MemorySystem(supabase, openai_client, memories_table)
        prompt_engine = PromptEngine(request.conversation_id, memories_table)

        # 1. 執行所有「讀取」任務（這必須是同步的）
        recalled_memories = await memory_system.recall_memories(...)
        conversation_history = memory_system.get_conversation_history(...)
        file_content = "" # 從 Redis 檢索檔案內容的邏輯也保留

        messages, emotion_analysis = await prompt_engine.build_prompt(
            request.user_message, recalled_memories, conversation_history, file_content
        )

        # 2. 呼叫 OpenAI 獲得回覆（主流程的等待點）
        assistant_message = await generate_response(
            openai_client, messages, model="gpt-4o-mini", max_tokens=1000, temperature=0.8
        )
        
        # 3. [重要] 保持核心記憶立即儲存 (確保主訊息不會丟失)
        await memory_system.save_memory(
            request.conversation_id, request.user_message, assistant_message,
            emotion_analysis, ai_id=os.getenv("AI_ID", "xiaochenguang_v1")
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
        # 保持你的錯誤處理邏輯
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(f"🔥 Chat Endpoint 發生嚴重錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="載體內部光流異常，請檢查日誌。")
