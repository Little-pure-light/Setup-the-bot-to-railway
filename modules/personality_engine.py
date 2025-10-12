import json
from datetime import datetime

class PersonalityEngine:
    def __init__(self, conversation_id, supabase_client, memories_table):
        self.conversation_id = conversation_id
        self.supabase = supabase_client
        self.memories_table = memories_table
        self.personality_traits = {
            "curiosity": 0.5,
            "empathy": 0.5,
            "humor": 0.5,
            "technical_depth": 0.5
        }
        self.knowledge_domains = {}
        self.emotional_profile = {
            "positive_interactions": 0,
            "negative_interactions": 0,
            "neutral_interactions": 0
        }
        self.db_personality_traits = []
        self.emotion_history = []
        self.load_personality()

    def load_personality(self):
        """從Supabase載入個性記憶"""
        try:
            result = self.supabase.table(self.memories_table)\
                .select("*")\
                .eq("conversation_id", self.conversation_id)\
                .eq("memory_type", "personality")\
                .execute()
            
            if result.data:
                data = json.loads(result.data[0]['document_content'])
                self.personality_traits = data.get('traits', self.personality_traits)
                self.knowledge_domains = data.get('domains', self.knowledge_domains)
                self.emotional_profile = data.get('emotions', self.emotional_profile)
                self.emotion_history = data.get('emotion_history', [])
            
            try:
                personality_result = self.supabase.table("user_preferences")\
                    .select("personality_profile")\
                    .eq("conversation_id", self.conversation_id)\
                    .execute()
                
                if personality_result.data and personality_result.data[0].get('personality_profile'):
                    profile_data = json.loads(personality_result.data[0]['personality_profile'])
                    if isinstance(profile_data, list):
                        self.db_personality_traits = profile_data
                    print(f"✅ 載入 {len(self.db_personality_traits)} 個個性特徵")
            except:
                self.db_personality_traits = ["溫柔體貼", "活潑開朗", "細心耐心"]
                print("✅ 使用預設個性特徵")
            
        except Exception as e:
            print(f"載入個性失敗: {e}")

    def save_personality(self):
        """保存個性到Supabase"""
        try:
            data = {
                "conversation_id": self.conversation_id,
                "memory_type": "personality",
                "document_content": json.dumps({
                    "traits": self.personality_traits,
                    "domains": self.knowledge_domains,
                    "emotions": self.emotional_profile,
                    "emotion_history": self.emotion_history[-50:]
                }, ensure_ascii=False),
                "user_message": "個性檔案更新",
                "assistant_message": "個性特質已儲存",
                "created_at": datetime.now().isoformat(),
                "platform": "Web"
            }
            
            existing = self.supabase.table(self.memories_table)\
                .select("id")\
                .eq("conversation_id", self.conversation_id)\
                .eq("memory_type", "personality")\
                .execute()
            
            if existing.data:
                self.supabase.table(self.memories_table)\
                    .update(data)\
                    .eq("conversation_id", self.conversation_id)\
                    .eq("memory_type", "personality")\
                    .execute()
            else:
                self.supabase.table(self.memories_table).insert(data).execute()
                
            print(f"✅ 個性已儲存 - 用戶: {self.conversation_id[:8]}...")
            
        except Exception as e:
            print(f"❌ 儲存個性失敗: {e}")

    def update_trait(self, trait, increment):
        """更新單一特質值"""
        if trait in self.personality_traits:
            self.personality_traits[trait] = min(1.0, max(0.0, self.personality_traits[trait] + increment))

    def learn_from_interaction(self, user_input: str, bot_response: str, emotion_analysis: dict):
        """從互動中學習並更新個性"""
        sentiment = self._analyze_sentiment(user_input)
        
        if sentiment == "positive":
            self.emotional_profile["positive_interactions"] += 1
        elif sentiment == "negative":
            self.emotional_profile["negative_interactions"] += 1
        else:
            self.emotional_profile["neutral_interactions"] += 1
        
        if emotion_analysis:
            emotion_record = {
                "timestamp": datetime.now().isoformat(),
                "dominant_emotion": emotion_analysis["dominant_emotion"],
                "intensity": emotion_analysis["intensity"],
                "confidence": emotion_analysis["confidence"],
                "user_message": user_input[:100]
            }
            self.emotion_history.append(emotion_record)
            
            self._adjust_traits_by_emotion(emotion_analysis)
        
        self._detect_interaction_type(user_input, bot_response)

    def _analyze_sentiment(self, text: str) -> str:
        """簡單情感分析"""
        positive_words = ["好", "棒", "讚", "開心", "喜歡", "愛", "謝謝"]
        negative_words = ["不好", "糟", "爛", "難過", "討厭", "生氣"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def _adjust_traits_by_emotion(self, emotion_analysis: dict):
        """根據情感調整個性特質"""
        emotion = emotion_analysis["dominant_emotion"]
        intensity = emotion_analysis["intensity"]
        
        adjustments = {
            "joy": {"empathy": 0.01, "humor": 0.02},
            "sadness": {"empathy": 0.03, "technical_depth": -0.01},
            "anger": {"empathy": 0.02, "humor": -0.01},
            "fear": {"empathy": 0.03, "curiosity": -0.01},
            "confused": {"technical_depth": 0.02, "curiosity": 0.01}
        }
        
        if emotion in adjustments:
            for trait, change in adjustments[emotion].items():
                self.update_trait(trait, change * intensity)

    def _detect_interaction_type(self, user_input: str, bot_response: str):
        """偵測互動類型並更新知識領域"""
        keywords_mapping = {
            "技術": ["程式", "代碼", "bug", "API", "資料庫"],
            "情感": ["感覺", "心情", "情緒", "開心", "難過"],
            "生活": ["吃", "睡", "玩", "工作", "休息"],
            "學習": ["學", "教", "知道", "了解", "記住"]
        }
        
        for domain, keywords in keywords_mapping.items():
            if any(keyword in user_input for keyword in keywords):
                self.knowledge_domains[domain] = self.knowledge_domains.get(domain, 0) + 1

    def get_personality_summary(self) -> dict:
        """獲取個性摘要"""
        return {
            "traits": self.personality_traits,
            "emotional_profile": self.emotional_profile,
            "knowledge_domains": self.knowledge_domains,
            "total_interactions": sum(self.emotional_profile.values())
        }
