from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# 模組引用（根據妳的專案結構）
from openai_handler import generate_response
from memory_system import memory_system

# ------------------------------------------------------
# 🌟 FastAPI 初始化
# ------------------------------------------------------
app = FastAPI(
    title="小宸光 AI 靈魂系統 API",
    version="1.0.0",
    description="整合情緒分析、記憶、人格模型的靈魂型 AI 系統",
)

# ------------------------------------------------------
# 🌐 CORS 設定（允許前端網頁或其他系統連線）
# ------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 可改成妳的網域，例如 https://xiaochenguang.ai
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------
# 🏠 測試根路由
# ------------------------------------------------------
@app.get("/")
def root():
    return {
        "message": "小宸光 AI 靈魂系統 API",
        "version": "1.0.0",
        "status": "running"
    }

# ------------------------------------------------------
# 💬 聊天 API
# ------------------------------------------------------
@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()

    user_message = data.get("user_message")
    user_id = data.get("user_id", "default_user")
    conversation_id = data.get("conversation_id", "default_conversation")

    if not user_message:
        return {"error": "Missing required field: user_message"}

    # 產生 AI 回覆
    ai_message = await generate_response(
        client=memory_system.openai_client,
        messages=[{"role": "user", "content": user_message}]
    )

    # 儲存情緒狀態
    emotion = await memory_system.save_emotional_state(user_id, ai_message)

    return {
        "assistant_message": ai_message,
        "emotion_analysis": emotion,
        "conversation_id": conversation_id
    }

# ------------------------------------------------------
# 💾 記憶 API
# ------------------------------------------------------
@app.get("/api/memory/{user_id}")
async def get_memory(user_id: str):
    memories = await memory_system.retrieve_user_memories(user_id)
    return {"user_id": user_id, "memories": memories}


# ------------------------------------------------------
# 🚀 啟動設定（自動讀取 Railway 提供的 PORT）
# ------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
