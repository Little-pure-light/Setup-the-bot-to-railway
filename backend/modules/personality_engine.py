"""
人格學習引擎 (Personality Engine)
根據互動歷史動態調整人格參數
"""
from typing import Dict, Any

class PersonalityEngine:
    def __init__(self):
        # 初始動態特質 (會隨互動改變)
        self.traits = {
            "curiosity": 0.5,
            "empathy": 0.5,
            "humor": 0.5,
            "technical_depth": 0.5
        }

        # 調整規則矩陣
        self.adjustment_rules = {
            "joy": {"empathy": 0.01, "humor": 0.02},
            "sadness": {"empathy": 0.03, "humor": -0.01},
            "anger": {"empathy": 0.02, "humor": -0.01, "curiosity": 0.01},
            "fear": {"empathy": 0.03, "technical_depth": -0.01},
            "confused": {"technical_depth": 0.02, "curiosity": 0.01},
            "love": {"empathy": 0.02, "humor": 0.01}
        }

    def learn_from_interaction(self, user_input: str, bot_response: str, emotion_analysis: Dict[str, Any]) -> Dict[str, float]:
        """從一次互動中學習並調整人格特質"""

        dominant_emotion = emotion_analysis.get("dominant_emotion", "neutral")
        intensity = emotion_analysis.get("intensity", 0.5)

        # 根據情緒類型調整
        if dominant_emotion in self.adjustment_rules:
            changes = self.adjustment_rules[dominant_emotion]
            for trait, delta in changes.items():
                # 強度越高，改變幅度越大
                actual_delta = delta * intensity
                if trait in self.traits:
                    self.traits[trait] = max(0.0, min(1.0, self.traits[trait] + actual_delta))

        # 根據用戶輸入內容微調 (簡單關鍵詞檢測)
        if "為什麼" in user_input or "解釋" in user_input:
            self.traits["technical_depth"] = min(1.0, self.traits["technical_depth"] + 0.01)

        if "哈哈" in user_input or "好笑" in user_input:
            self.traits["humor"] = min(1.0, self.traits["humor"] + 0.01)

        return self.traits

    def get_current_traits(self) -> Dict[str, float]:
        return self.traits
