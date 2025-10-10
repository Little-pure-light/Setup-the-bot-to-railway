import os
import json
from fastapi import FastAPI, HTTPException
from modules.chat_module import ChatModule
from modules.memory_module import MemoryModule
from modules.emotion_module import EmotionModule
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 部署時請改為限定網域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔽🔽🔽 嘗試載入 user_profile.json 🔽🔽🔽
profile_path = os.path.join(os.path.dirname(__file__), "Profile", "user_profile.json")
try:
    with open(profile_path, "r", encoding="utf-8") as file:
        user_profile = json.load(file)
except FileNotFoundError:
    print("⚠️ 無法載入 user_profile.json：找不到 user_profile.json，將使用預設設定")
    user_profile = {
        "user_id": "default_user",
        "user_name": "預設使用者",
        "preferences": {}
    }

# 模組初始化
chat_module = ChatModule(user_profile)
memory_module = MemoryModule()
emotion_module = EmotionModule()

class ChatRequest(BaseModel):
    user_message: str
    conversation_id: str
    user_id: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        reply = chat_module.process_user_message(
            request.user_message,
            request.conversation_id,
            request.user_id
        )
        return {"response": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memories/{conversation_id}")
async def get_memories(conversation_id: str, limit: int = 10):
    return memory_module.get_conversation_memory(conversation_id, limit)

@app.get("/api/emotional-states/{user_id}")
async def get_emotional_states(user_id: str, limit: int = 10):
    return emotion_module.get_user_emotional_states(user_id, limit)
