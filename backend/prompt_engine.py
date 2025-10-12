import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from modules.soul import XiaoChenGuangSoul
from modules.emotion_detector import EnhancedEmotionDetector
from modules.personality_engine import PersonalityEngine
from backend.supabase_handler import get_supabase
supabase_client = get_supabase()
router = APIRouter()

class PromptRequest(BaseModel):
    conversation_id: str
    user_message: str

class PromptEngine:
    def __init__(self, conversation_id: str, supabase_client, memories_table: str):
        self.soul = XiaoChenGuangSoul()
        self.emotion_detector = EnhancedEmotionDetector()
        self.personality_engine = PersonalityEngine(conversation_id, supabase_client, memories_table)

    # prompt_engine.py - 只需要移除參數

class PromptEngine:
    def __init__(self, conversation_id: str, memories_table: str): # 移除 supabase_client
        self.soul = XiaoChenGuangSoul()
        self.emotion_detector = EnhancedEmotionDetector()
        # 這裡直接用檔案頂部已經實例化好的 supabase_client
        self.personality_engine = PersonalityEngine(conversation_id, supabase_client, memories_table)
    
    def build_prompt(self, user_message: str, recalled_memories: str = "", 
                    conversation_history: str = "") -> tuple[list, dict]:
        emotion_analysis = self.emotion_detector.analyze_emotion(user_message)
        emotion_style = self.emotion_detector.get_emotion_response_style(emotion_analysis)

        personality_prompt = self.soul.generate_personality_prompt(emotion_style)

        system_prompt = f"""{personality_prompt}

### 記憶與上下文
{recalled_memories if recalled_memories else "（無相關記憶）"}

### 最近對話歷史
{conversation_history if conversation_history else "（這是對話開始）"}

### 當前情感分析
- 主要情緒: {emotion_analysis["dominant_emotion"]}
- 強度: {emotion_analysis["intensity"]:.2f}
- 信心度: {emotion_analysis["confidence"]:.2f}
- 回應語調: {emotion_style["tone"]}
- 同理心等級: {emotion_style["empathy_level"]:.2f}
- 能量等級: {emotion_style["energy_level"]:.2f}

請根據以上所有資訊，以小宸光的身份回應用戶，展現出對應的情感理解與個性特質。
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        return messages, emotion_analysis

# 如果你想要在 prompt_engine.py 中開放一個 API，可以取消註解以下範例：

# @router.post("/api/prompt")
# async def generate_prompt(req: PromptRequest):
#     try:
#         engine = PromptEngine(req.conversation_id, supabase_client, "memories")
#         messages, emotions = engine.build_prompt(req.user_message)
#         return {"messages": messages, "emotions": emotions}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

