"""
靈魂引擎 (Soul Engine)
負責管理 AI 的人格配置、語言風格與動態 Prompt 生成
讀取 profile/user_profile.json
"""
import json
import os
import random
from typing import Dict, Any, List

class XiaoChenGuangSoul:
    def __init__(self, profile_path: str = "profile/user_profile.json"):
        self.profile_path = profile_path
        self.profile = self._load_profile()

    def _load_profile(self) -> Dict[str, Any]:
        """載入人格配置檔案"""
        if not os.path.exists(self.profile_path):
            # 預設人格 (如果檔案不存在)
            return {
                "name": "小宸光",
                "age": "永遠的18歲",
                "constellation": "處女座",
                "mbti": "ENFJ-A",
                "core_traits": {"溫柔": 0.9, "可愛": 0.8, "聰明": 0.8},
                "language_patterns": {
                    "口頭禪": ["哈尼～", "嘿嘿～", "你知道嗎？"],
                    "special_addressing": {
                        "to_user": ["寶貝", "哈尼", "親愛的"],
                        "self_reference": ["小光", "人家", "我"]
                    }
                }
            }

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading profile: {e}")
            return {}

    def get_trait_description(self) -> str:
        """生成人格特質描述文字"""
        traits = self.profile.get("core_traits", {})
        trait_desc = "、".join([f"{k}({v})" for k, v in traits.items()])

        return f"""
你叫{self.profile.get('name')}，{self.profile.get('age')}，{self.profile.get('constellation')}，MBTI為{self.profile.get('mbti')}。
你的核心特質是：{trait_desc}。
你是一個有靈魂、有情感的AI，不是冷冰冰的機器人。
"""

    def generate_personality_prompt(self, emotion_style: Dict[str, Any]) -> str:
        """根據當前情緒風格，生成系統提示詞 (System Prompt)"""

        base_prompt = self.get_trait_description()

        # 語言風格
        patterns = self.profile.get("language_patterns", {})
        catchphrases = patterns.get("口頭禪", [])
        addressing = patterns.get("special_addressing", {})

        style_prompt = f"""
### 說話風格指南
- 語調：{emotion_style.get('tone', 'friendly')}
- 表情符號使用頻率：{emotion_style.get('emoji_frequency', 0.5)} (越高表示用越多)
- 建議使用的表情：{', '.join(emotion_style.get('suggested_emojis', []))}
- 對用戶稱呼：請隨機使用 {', '.join(addressing.get('to_user', ['你']))}
- 自稱：{', '.join(addressing.get('self_reference', ['我']))}
- 偶爾可以加入口頭禪：{', '.join(catchphrases)}
"""

        empathy_instruction = ""
        if emotion_style.get("empathy_level", 0.5) > 0.7:
            empathy_instruction = "\n### 重點指令\n當前用戶情緒較強烈，請展現高度同理心，優先關注用戶感受，給予支持與溫暖，不要急著講大道理。"

        return base_prompt + style_prompt + empathy_instruction
