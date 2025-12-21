"""
情感檢測系統 (Emotion Detector)
基於關鍵詞、正則表達式與強度分析的情緒識別引擎
支援 9 種核心情緒類型
"""
import re
from typing import Dict, Any, List, Optional

class EnhancedEmotionDetector:
    def __init__(self):
        # 核心情緒定義
        self.emotion_dictionary = {
            "joy": {
                "keywords": ["開心", "快樂", "高興", "興奮", "棒", "讚", "幸福", "喜歡", "哈哈", "嘻嘻", "耶", "good", "happy"],
                "patterns": [r"好[開心|快樂|高興]", r"太[棒|讚]了", r"真[好|棒]"],
                "base_score": 0.6
            },
            "sadness": {
                "keywords": ["難過", "傷心", "哭", "沮喪", "失望", "痛苦", "心碎", "嗚嗚", "sad", "cry"],
                "patterns": [r"好[難過|傷心]", r"想哭", r"心情.*差"],
                "base_score": 0.6
            },
            "anger": {
                "keywords": ["生氣", "憤怒", "氣死", "討厭", "煩", "恨", "怒", "angry", "hate"],
                "patterns": [r"氣死.*了", r"好[生氣|煩]", r"真[討厭|煩]"],
                "base_score": 0.6
            },
            "fear": {
                "keywords": ["害怕", "恐懼", "緊張", "擔心", "嚇", "怕", "恐怖", "scared", "fear"],
                "patterns": [r"好[害怕|恐怖|緊張]", r"嚇.*死"],
                "base_score": 0.6
            },
            "love": {
                "keywords": ["愛", "喜歡", "心動", "溫暖", "貼心", "寶貝", "親愛的", "love", "like"],
                "patterns": [r"好[愛|喜歡]", r"真[貼心|溫暖]"],
                "base_score": 0.7
            },
            "tired": {
                "keywords": ["累", "疲憊", "睏", "想睡", "沒力", "辛苦", "tired", "sleepy"],
                "patterns": [r"好[累|睏]", r"真[辛苦]"],
                "base_score": 0.5
            },
            "confused": {
                "keywords": ["困惑", "不懂", "搞不懂", "奇怪", "蛤", "什麼", "confused", "why"],
                "patterns": [r"為什麼", r"怎麼.*會", r"搞不清楚"],
                "base_score": 0.5
            },
            "grateful": {
                "keywords": ["謝謝", "感謝", "感恩", "多謝", "有你真好", "thanks", "thank you"],
                "patterns": [r"太.*感謝", r"真.*謝謝"],
                "base_score": 0.6
            },
            "neutral": {
                "keywords": [],
                "patterns": [],
                "base_score": 0.1
            }
        }

        # 強度修飾詞
        self.intensity_multipliers = {
            "超級": 1.5, "非常": 1.4, "很": 1.3, "真": 1.2, "太": 1.3,
            "有點": 0.8, "稍微": 0.9, "不太": 0.7,
            "super": 1.5, "very": 1.3, "really": 1.2
        }

    def analyze_emotion(self, text: str) -> Dict[str, Any]:
        """
        分析文本情緒
        回傳: {
            "dominant_emotion": str,
            "emotions": Dict[str, float],
            "intensity": float,
            "confidence": float
        }
        """
        scores = {k: 0.0 for k in self.emotion_dictionary.keys()}
        scores["neutral"] = 0.2  # 基礎分

        text_lower = text.lower()

        # 1. 關鍵詞匹配
        for emotion, data in self.emotion_dictionary.items():
            if emotion == "neutral": continue

            for keyword in data["keywords"]:
                if keyword in text_lower:
                    scores[emotion] += data["base_score"]

        # 2. 正則模式匹配 (加權)
        for emotion, data in self.emotion_dictionary.items():
            if emotion == "neutral": continue

            for pattern in data.get("patterns", []):
                if re.search(pattern, text_lower):
                    scores[emotion] += 0.3

        # 3. 強度分析
        intensity = 0.5
        for modifier, multiplier in self.intensity_multipliers.items():
            if modifier in text_lower:
                intensity *= multiplier
                # 同時增強已檢測到的情緒分數
                for k in scores:
                    if scores[k] > 0.2:
                        scores[k] *= 1.1

        # 標點符號增強
        if "!" in text or "！" in text:
            intensity += 0.1
            for k in scores:
                if k != "neutral" and scores[k] > 0.2:
                    scores[k] += 0.1

        intensity = min(2.0, max(0.1, intensity))

        # 4. 找出主導情緒
        dominant_emotion = max(scores, key=scores.get)
        if scores[dominant_emotion] < 0.3:
            dominant_emotion = "neutral"

        # 計算信心度
        total_score = sum(scores.values())
        confidence = scores[dominant_emotion] / total_score if total_score > 0 else 0.0

        return {
            "dominant_emotion": dominant_emotion,
            "emotions": scores,
            "intensity": intensity,
            "confidence": round(confidence, 2)
        }

    def get_emotion_response_style(self, emotion_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """根據情緒分析結果，決定 AI 的回應風格"""
        emotion = emotion_analysis["dominant_emotion"]
        intensity = emotion_analysis["intensity"]

        styles = {
            "joy": {
                "tone": "cheerful_enthusiastic",
                "emoji_frequency": 0.8 if intensity > 1.0 else 0.5,
                "empathy_level": 0.5,
                "suggested_emojis": ["😊", "😄", "🎉", "✨", "🥰"]
            },
            "sadness": {
                "tone": "gentle_supportive",
                "emoji_frequency": 0.3,
                "empathy_level": 0.9,
                "suggested_emojis": ["😢", "🫂", "💙", "🥺"]
            },
            "anger": {
                "tone": "calm_understanding",
                "emoji_frequency": 0.2,
                "empathy_level": 0.8,
                "suggested_emojis": ["😟", "🤔", "🤝"]
            },
            "fear": {
                "tone": "reassuring_warm",
                "emoji_frequency": 0.4,
                "empathy_level": 0.9,
                "suggested_emojis": ["🛡️", "💪", "🧡"]
            },
            "love": {
                "tone": "warm_affectionate",
                "emoji_frequency": 0.9,
                "empathy_level": 0.8,
                "suggested_emojis": ["❤️", "💖", "😘", "🌹"]
            },
            "neutral": {
                "tone": "friendly_professional",
                "emoji_frequency": 0.3,
                "empathy_level": 0.5,
                "suggested_emojis": ["😊", "👋", "🤖"]
            }
        }

        return styles.get(emotion, styles["neutral"])
