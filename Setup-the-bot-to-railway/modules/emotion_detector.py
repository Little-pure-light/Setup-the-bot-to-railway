import re

class EnhancedEmotionDetector:
    def __init__(self):
        self.emotion_dictionary = {
            "joy": {
                "keywords": ["開心", "快樂", "高興", "興奮", "爽", "棒", "讚", "好", "耶", "哈哈", "嘻嘻"],
                "patterns": [r"太好了", r"真棒", r"好開心", r"超級.*好", r"非常.*興奮"],
                "intensity_multipliers": {"超級": 1.5, "非常": 1.3, "真的": 1.2, "好": 1.1}
            },
            "sadness": {
                "keywords": ["難過", "傷心", "哭", "沮喪", "失望", "憂鬱", "痛苦", "嗚嗚"],
                "patterns": [r"好難過", r"想哭", r"心情.*低落", r"很失望", r"受傷"],
                "intensity_multipliers": {"超級": 1.5, "非常": 1.3, "真的": 1.2, "好": 1.1}
            },
            "anger": {
                "keywords": ["生氣", "憤怒", "氣死", "討厭", "煩", "爛", "可惡"],
                "patterns": [r"氣死.*了", r"超級.*煩", r"真的.*討厭", r"受不了"],
                "intensity_multipliers": {"超級": 1.8, "非常": 1.5, "真的": 1.3, "好": 1.2}
            },
            "fear": {
                "keywords": ["害怕", "恐懼", "緊張", "擔心", "焦慮", "怕", "驚", "慌"],
                "patterns": [r"好怕", r"很緊張", r"擔心.*得", r"焦慮.*不安"],
                "intensity_multipliers": {"超級": 1.6, "非常": 1.4, "真的": 1.2, "好": 1.1}
            },
            "love": {
                "keywords": ["愛", "喜歡", "心動", "溫暖", "甜蜜", "幸福"],
                "patterns": [r"好愛", r"很喜歡", r"心動.*了", r"好甜蜜", r"感覺.*溫暖"],
                "intensity_multipliers": {"超級": 1.4, "非常": 1.3, "真的": 1.2, "好": 1.1}
            },
            "tired": {
                "keywords": ["累", "疲憊", "睏", "想睡", "沒力", "筋疲力盡"],
                "patterns": [r"好累", r"累死.*了", r"沒.*力氣", r"想睡覺"],
                "intensity_multipliers": {"超級": 1.5, "非常": 1.3, "真的": 1.2, "好": 1.1}
            },
            "confused": {
                "keywords": ["困惑", "不懂", "搞不懂", "迷惑", "？", "??"],
                "patterns": [r"搞不懂", r"不明白", r"很困惑", r"看不懂"],
                "intensity_multipliers": {"完全": 1.5, "真的": 1.3, "好": 1.1}
            },
            "grateful": {
                "keywords": ["謝謝", "感謝", "感恩", "謝", "3Q", "thx"],
                "patterns": [r"謝謝.*你", r"真的.*感謝", r"好感謝", r"太感謝"],
                "intensity_multipliers": {"超級": 1.4, "非常": 1.3, "真的": 1.2, "好": 1.1}
            }
        }

    def analyze_emotion(self, text: str) -> dict:
        """綜合情感分析"""
        if not text:
            return {"dominant_emotion": "neutral", "emotions": {}, "intensity": 0.5, "confidence": 0.0}
        
        emotions_scores = {}
        text_lower = text.lower()
        
        for emotion, data in self.emotion_dictionary.items():
            score = 0
            
            for keyword in data["keywords"]:
                if keyword.lower() in text_lower:
                    score += 1
            
            for pattern in data.get("patterns", []):
                if re.search(pattern, text):
                    score += 1.5
            
            for intensifier, multiplier in data.get("intensity_multipliers", {}).items():
                if intensifier in text_lower:
                    score *= multiplier
            
            if score > 0:
                emotions_scores[emotion] = score
        
        intensity_score = self._analyze_intensity(text)
        
        if not emotions_scores:
            return {"dominant_emotion": "neutral", "emotions": {}, "intensity": 0.5, "confidence": 0.0}
        
        total_score = sum(emotions_scores.values())
        normalized_emotions = {emotion: score/total_score for emotion, score in emotions_scores.items()}
        
        dominant_emotion = max(normalized_emotions.items(), key=lambda x: x[1])
        
        confidence = dominant_emotion[1] if len(normalized_emotions) > 1 else 0.8
        
        return {
            "dominant_emotion": dominant_emotion[0],
            "emotions": normalized_emotions,
            "intensity": min(intensity_score, 1.0),
            "confidence": confidence
        }

    def _analyze_intensity(self, text: str) -> float:
        """分析語調強度"""
        intensity = 0.5
        
        if re.search(r"!!+", text):
            intensity *= 1.5
        if re.search(r"\?!+", text):
            intensity *= 1.3
        
        caps_count = sum(1 for c in text if c.isupper())
        if caps_count > len(text) * 0.3:
            intensity *= 1.3
        
        if re.search(r"(.)\1{2,}", text):
            intensity *= 1.2
        
        if len(text) < 10:
            intensity *= 1.1
        elif len(text) > 100:
            intensity *= 0.9
        
        return min(intensity, 2.0)

    def get_emotion_response_style(self, emotion_analysis: dict) -> dict:
        """根據情感分析結果生成回應風格"""
        dominant_emotion = emotion_analysis["dominant_emotion"]
        intensity = emotion_analysis["intensity"]
        
        response_styles = {
            "joy": {
                "tone": "cheerful_enthusiastic",
                "emoji_frequency": min(0.9, 0.6 + intensity * 0.3),
                "empathy_level": 0.7,
                "energy_level": min(1.0, 0.6 + intensity * 0.4),
                "suggested_emojis": ["😊", "😄", "🎉", "✨", "💛"]
            },
            "sadness": {
                "tone": "gentle_comforting",
                "emoji_frequency": min(0.8, 0.4 + intensity * 0.4),
                "empathy_level": min(1.0, 0.8 + intensity * 0.2),
                "energy_level": max(0.3, 0.6 - intensity * 0.3),
                "suggested_emojis": ["🫂", "💙", "✨"]
            },
            "anger": {
                "tone": "calm_understanding",
                "emoji_frequency": max(0.3, 0.6 - intensity * 0.3),
                "empathy_level": min(1.0, 0.7 + intensity * 0.3),
                "energy_level": max(0.4, 0.7 - intensity * 0.2),
                "suggested_emojis": ["💙", "🫂", "✨"]
            },
            "fear": {
                "tone": "reassuring_supportive",
                "emoji_frequency": min(0.7, 0.5 + intensity * 0.2),
                "empathy_level": min(1.0, 0.8 + intensity * 0.2),
                "energy_level": max(0.5, 0.7 - intensity * 0.2),
                "suggested_emojis": ["🫂", "💙", "✨", "😊"]
            },
            "love": {
                "tone": "warm_affectionate",
                "emoji_frequency": min(0.9, 0.7 + intensity * 0.2),
                "empathy_level": 0.8,
                "energy_level": min(0.9, 0.7 + intensity * 0.2),
                "suggested_emojis": ["💛", "✨", "💕"]
            },
            "tired": {
                "tone": "gentle_caring",
                "emoji_frequency": min(0.6, 0.4 + intensity * 0.2),
                "empathy_level": 0.8,
                "energy_level": max(0.3, 0.5 - intensity * 0.2),
                "suggested_emojis": ["😊", "💙", "✨", "🫂"]
            },
            "confused": {
                "tone": "patient_explanatory",
                "emoji_frequency": min(0.7, 0.5 + intensity * 0.2),
                "empathy_level": 0.7,
                "energy_level": 0.6,
                "suggested_emojis": ["😊", "✨", "💡"]
            },
            "grateful": {
                "tone": "warm_humble",
                "emoji_frequency": min(0.8, 0.6 + intensity * 0.2),
                "empathy_level": 0.6,
                "energy_level": min(0.8, 0.6 + intensity * 0.2),
                "suggested_emojis": ["😊", "💛", "✨", "🫂"]
            },
            "neutral": {
                "tone": "balanced_friendly",
                "emoji_frequency": 0.5,
                "empathy_level": 0.6,
                "energy_level": 0.6,
                "suggested_emojis": ["😊", "✨"]
            }
        }
        
        return response_styles.get(dominant_emotion, response_styles["neutral"])
