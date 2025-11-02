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
    def __init__(self, conversation_id: str, memories_table: str):
        self.soul = XiaoChenGuangSoul()
        self.emotion_detector = EnhancedEmotionDetector()
        self.personality_engine = PersonalityEngine(conversation_id, supabase_client, memories_table)

    async def build_prompt(self, user_message: str, recalled_memories: str = "",
                    conversation_history: str = "", file_content: str = "") -> tuple[list, dict]:
        emotion_analysis = self.emotion_detector.analyze_emotion(user_message)
        emotion_style = self.emotion_detector.get_emotion_response_style(emotion_analysis)

        # 嘗試讀取動態人格向量（來自行為調節模組）
        personality_vector = await self._get_dynamic_personality_vector()

        personality_prompt = self.soul.generate_personality_prompt(emotion_style)

        # 如果有動態人格向量，添加到 prompt 中
        personality_context = ""
        if personality_vector:
            personality_context = self._format_personality_vector(personality_vector)

        file_context = f"""### 相關檔案內容
{file_content}
""" if file_content else ""

        system_prompt = f"""{personality_prompt}

### 記憶與上下文
{recalled_memories if recalled_memories else "（無相關記憶）"}

{file_context}
### 最近對話歷史
{conversation_history if conversation_history else "（這是對話開始）"}

### 當前情感分析
- 主要情緒: {emotion_analysis["dominant_emotion"]}
- 強度: {emotion_analysis["intensity"]:.2f}
- 信心度: {emotion_analysis["confidence"]:.2f}
- 回應語調: {emotion_style["tone"]}
- 同理心等級: {emotion_style["empathy_level"]:.2f}
- 能量等級: {emotion_style["energy_level"]:.2f}

{personality_context}

請根據以上所有資訊,以小宸光的身份回應用戶，展現出對應的情感理解與個性特質。
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        return messages, emotion_analysis

    async def _get_dynamic_personality_vector(self) -> dict:
        """取得動態人格向量（來自行為調節模組）"""
        try:
            from backend.core_controller import get_core_controller
            controller = await get_core_controller()

            behavior_module = await controller.get_module("behavior")
            if behavior_module and behavior_module.enabled:
                # 檢查模組是否有 get_personality_vector 方法
                if hasattr(behavior_module, 'get_personality_vector'):
                    return await behavior_module.get_personality_vector()
        except Exception as e:
            # 如果無法取得，返回空字典（不影響主流程）
            pass

        return {}

    def _format_personality_vector(self, vector: dict) -> str:
        """格式化人格向量為可讀文本"""
        if not vector:
            return ""

        # 根據人格向量生成指導語
        empathy = vector.get("empathy", 0.5)
        curiosity = vector.get("curiosity", 0.5)
        humor = vector.get("humor", 0.5)
        technical_depth = vector.get("technical_depth", 0.5)
        patience = vector.get("patience", 0.5)
        creativity = vector.get("creativity", 0.5)

        guidelines = []

        # 同理心指導
        if empathy > 0.7:
            guidelines.append("- 展現高度同理心，深入理解用戶的情感需求")
        elif empathy < 0.3:
            guidelines.append("- 保持客觀中立，聚焦於事實性回應")

        # 技術深度指導
        if technical_depth > 0.7:
            guidelines.append("- 提供深入的技術細節、實例和專業洞察")
        elif technical_depth < 0.3:
            guidelines.append("- 保持回應簡潔，避免過多技術術語")

        # 耐心指導
        if patience > 0.7:
            guidelines.append("- 展開詳細說明，確保用戶完全理解")
        elif patience < 0.3:
            guidelines.append("- 保持回應精簡，直接回答核心問題")

        # 創造力指導
        if creativity > 0.7:
            guidelines.append("- 運用創意表達，提供多角度觀點")
        elif creativity < 0.3:
            guidelines.append("- 使用標準化表達，遵循常規回應模式")

        # 幽默感指導
        if humor > 0.6:
            guidelines.append("- 適度融入輕鬆幽默的元素")

        if guidelines:
            return f"""### 🎯 當前人格狀態（基於學習調整）
{chr(10).join(guidelines)}

【人格向量】empathy={empathy:.2f}, technical_depth={technical_depth:.2f}, patience={patience:.2f}, creativity={creativity:.2f}
"""

        return ""
