import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio

# 調整 sys.path 以包含 backend/ 和 models/ 資料夾
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models'))

from backend.supabase_handler import get_supabase_client
from backend.openai_handler import get_openai_client, generate_response
from models.memory_system import MemorySystem
from models.emotion_detector import EnhancedEmotionDetector
from models.personality_engine import PersonalityEngine

from backend.chat_router import router as chat_router
from backend.memory_router import router as memory_router
from backend.file_upload import router as file_router

app = FastAPI(title="小宸光 AI 靈魂系統 Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(memory_router, prefix="/api", tags=["Memory"])
app.include_router(file_router, prefix="/api", tags=["File"])

class ChatRequest(BaseModel):
    user_message: str
    conversation_id: str
    user_id: str = "default_user"

class ChatResponse(BaseModel):
    assistant_message: str
    emotion_analysis: dict
    conversation_id: str

# 初始化全局依賴（參照 xiaochenguang_memories 和 emotional_states 資料表）
supabase = get_supabase_client()
openai_client = get_openai_client()
memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
memory_system = MemorySystem(supabase, openai_client, memories_table)
emotion_detector = EnhancedEmotionDetector()
personality_engine = PersonalityEngine(conversation_id=None, supabase_client=supabase, memories_table=memories_table)

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """處理聊天請求並整合記憶、情緒、個性邏輯"""
    try:
        # 更新 PersonalityEngine 的 conversation_id
        personality_engine.conversation_id = request.conversation_id

        # 情緒分析
        emotion_analysis = emotion_detector.analyze_emotion(request.user_message)
        emotion_style = emotion_detector.get_emotion_response_style(emotion_analysis)

        # 召回記憶
        recalled_memories = await memory_system.recall_memories(request.user_message, request.conversation_id)
        conversation_history = memory_system.get_conversation_history(request.conversation_id, limit=5)

        # 構建提示語
        system_prompt = f"""### 記憶與上下文
{recalled_memories if recalled_memories else "（無相關記憶）"}

### 最近對話歷史
{conversation_history if conversation_history else "（這是對話開始）"}

### 當前情感分析
- 主要情緒: {emotion_analysis['dominant_emotion']}
- 強度: {emotion_analysis['intensity']:.2f}
- 信心度: {emotion_analysis['confidence']:.2f}
- 回應語調: {emotion_style['tone']}
- 同理心等級: {emotion_style['empathy_level']:.2f}
- 能量等級: {emotion_style['energy_level']:.2f}

請以小宸光的身份回應用戶，展現對應的情感理解與個性特質。
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.user_message}
        ]

        # 生成回應
        assistant_message = await generate_response(
            openai_client,
            messages,
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.8
        )

        # 記憶儲存（參照 xiaochenguang_memories 資料表）
        await memory_system.save_memory(
            request.conversation_id,
            request.user_message,
            assistant_message,
            emotion_analysis,
            ai_id=os.getenv("AI_ID", "xiaochenguang_v1")
        )

        # 儲存情緒狀態（參照 emotional_states 資料表）
        await memory_system.save_emotional_state(
            request.user_id,
            emotion_analysis,
            context=request.user_message
        )

        # 個性引擎學習
        personality_engine.learn_from_interaction(
            request.user_message,
            assistant_message,
            emotion_analysis
        )
        personality_engine.save_personality()

        return ChatResponse(
            assistant_message=assistant_message,
            emotion_analysis=emotion_analysis,
            conversation_id=request.conversation_id
        )

    except Exception as e:
        print(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "message": "小宸光 AI 靈魂系統 Bot",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
