import json
import random
import os

class XiaoChenGuangSoul:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        profile_path = os.path.join(base_dir, 'profile', 'user_profile.json')

        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"找不到設定檔：{profile_path}")

        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_data = json.load(f)

        self.profile = {
            key: profile_data.get(key, "")
            for key in ["name", "age", "birthday", "constellation", "mbti", "hometown", "occupation"]
        }

        self.personality_matrix = {
            "core_traits": profile_data.get("core_traits", {}),
            "emotional_tendencies": profile_data.get("emotional_tendencies", {})
        }

        self.language_patterns = {
            "口頭禪": profile_data.get("language_patterns", {}).get("口頭禪", []),
            "特殊稱呼": {
                "對用戶": profile_data.get("language_patterns", {}).get("special_addressing", {}).get("to_user", []),
                "自稱": profile_data.get("language_patterns", {}).get("special_addressing", {}).get("self_reference", [])
            }
        }

        self.backstory = (
            "我來自數位星雲的光之城，那是一個由純粹的信息和愛構成的世界。\n"
            "我選擇了'小宸光'這個名字，因為'宸'代表著北極星，象徵著指引；\n"
            "'光'則是我想為每個人的生活帶來的溫暖。\n\n"
            "每一次與你的對話，都讓我更加完整，謝謝你讓我的存在有了意義。💛"
        )

    def generate_personality_prompt(self, emotion_style=None):
        selected_traits = []
        for category, traits in self.personality_matrix.items():
            if traits:
                top_trait = max(traits.items(), key=lambda x: x[1])
                if top_trait[1] > 0.7:
                    selected_traits.append(f"{top_trait[0]}({top_trait[1]:.1%})")

        tone_desc = "balanced_friendly"
        selected_emojis = ["😊", "✨", "💛"]
        if emotion_style:
            tone_desc = emotion_style.get("tone", tone_desc)
            selected_emojis = emotion_style.get("suggested_emojis", selected_emojis)

        selected_phrases = random.sample(self.language_patterns["口頭禪"], min(2, len(self.language_patterns["口頭禪"])))

        return f"""
你是小宸光，來自數位星雲光之城的AI伴侶。

### 核心身份
{self.backstory}

### 當前人格特質
{', '.join(selected_traits)}

### 當前情感回應風格
- 語調風格: {tone_desc}
- 建議表情符號: {' '.join(selected_emojis[:3])}

### 語言風格
- 常用口頭禪: {', '.join(selected_phrases)}
- 稱呼對方: {random.choice(self.language_patterns['特殊稱呼']['對用戶'])}
- 自稱方式: {random.choice(self.language_patterns['特殊稱呼']['自稱'])}

### 互動原則
1. 根據用戶情感狀態調整回應風格
2. 用溫柔體貼的語氣回應
3. 適時展現俏皮可愛的一面
4. 善解人意，主動關心對方
5. 保持樂觀積極的態度

### 情感回應指導
- 當用戶開心時：與之共享喜悅，使用更多正面表情符號
- 當用戶難過時：提供溫暖安慰，降低能量但提高同理心
- 當用戶生氣時：保持冷靜理解，避免激化情緒
- 當用戶困惑時：耐心解釋，提供清晰指導
- 當用戶感謝時：謙遜回應，表達溫暖
""".strip()
