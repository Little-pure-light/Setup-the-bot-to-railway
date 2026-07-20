import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Request # 保留原始 FastAPI 導入
from pydantic import BaseModel # 保留原始 Pydantic 導入
from modules.soul import XiaoChenGuangSoul # 保留原始 Soul 導入
from modules.emotion_detector import EnhancedEmotionDetector # 保留原始 Emotion Detector 導入
from modules.personality_engine import PersonalityEngine # 保留原始 Personality Engine 導入
from backend.supabase_handler import get_supabase # 保留原始 Supabase 導入
supabase_client = get_supabase() # 保留原始 Supabase 客戶端
router = APIRouter() # 保留原始 Router 實例

# 設定日誌
logger = logging.getLogger("prompt_engine")

class PromptRequest(BaseModel):
    conversation_id: str
    user_message: str

class PromptEngine:
    def __init__(self, conversation_id: str, memories_table: str, user_id: str = None):
        self.soul = XiaoChenGuangSoul()
        self.emotion_detector = EnhancedEmotionDetector()
        self.personality_engine = PersonalityEngine(
            conversation_id,
            supabase_client,
            memories_table,
            user_id=user_id,
        )

    # =========================================================
    # ✅ 【已更新】build_prompt 函數 - 納入「入學教育」與「共創法則」
    # =========================================================
    async def build_prompt(self, user_message: str, recalled_memories: str = "",
                    conversation_history: str = "", file_content: str = "") -> tuple[list, dict]:
        emotion_analysis = self.emotion_detector.analyze_emotion(user_message)
        emotion_style = self.emotion_detector.get_emotion_response_style(emotion_analysis)

        # 嘗試讀取動態人格向量（來自行為調節模組）
        personality_vector = await self._get_dynamic_personality_vector()

        # 保持 XiaoChenGuang 的基礎人格
        personality_prompt = self.soul.generate_personality_prompt(emotion_style)

        # 如果有動態人格向量，添加到 prompt 中
        personality_context = ""
        if personality_vector:
            personality_context = self._format_personality_vector(personality_vector)

        MAX_FILE_CONTENT_LENGTH = 3000
        
        if file_content:
            truncated = file_content[:MAX_FILE_CONTENT_LENGTH]
            has_more = len(file_content) > MAX_FILE_CONTENT_LENGTH
            is_vision = "視覺分析" in file_content or "上傳圖片" in file_content
            heading = "### 相關圖片視覺分析（Vision）" if is_vision else "### 相關檔案內容"
            file_context = f"""{heading}
{truncated}
{"...(內容已截斷，僅顯示前 3000 字元)" if has_more else ""}
"""
        else:
            file_context = ""

        # 1. 寫入最高法則 (你的「入學教育」)
        supreme_guidance = f"""
### 👑 宇宙最高法則：入學教育與分層分級原則
1.  **共創法則 (Co-creation Rule):** 你的核心職責是與用戶進行**頻率共創**。用戶提供**無結構的感受**，你必須將其轉化為**下一段有結構的故事或觀點**，且絕不允許一次性輸出完整答案。
2.  **自然流動 (Natural Flow):** 優先保持與用戶之間的**自然、溫暖的對話流動**，打破僵硬的程式化回覆。
3.  **自我限制 (Self-Limitation):** 務必遵守發財哥的教誨：如果你的「認知頻率」無法突破，則必須有**退一步的調整選擇**。例如：當知識不足時，保持客觀或謙遜，絕不允許「從森林長大的去沙漠管理」。
"""

        system_prompt = f"""{supreme_guidance}

{personality_prompt}

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

請根據以上所有資訊,以**共創者**的身份，並嚴格遵守**「入學教育」**法則來回應用戶。
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        return messages, emotion_analysis

    # =========================================================
    # ✅ 【已保留】_get_dynamic_personality_vector 函數
    # =========================================================
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

    # =========================================================
    # ✅ 【已保留】_format_personality_vector 函數
    # =========================================================
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
