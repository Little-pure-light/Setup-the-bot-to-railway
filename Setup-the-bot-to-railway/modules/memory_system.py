from datetime import datetime
from typing import Optional
from modules.emotion_detector import EnhancedEmotionDetector

class MemorySystem:
    def __init__(self, supabase_client, openai_client, memories_table: str):
        self.supabase = supabase_client
        self.openai_client = openai_client
        self.memories_table = memories_table
        self.emotion_detector = EnhancedEmotionDetector()

    async def save_memory(self, conversation_id: str, user_input: str, bot_response: str, 
                         emotion_analysis: dict, file_name: Optional[str] = None, 
                         ai_id: str = "xiaochenguang_v1"):
        """添加或更新對話到記憶庫，包含 access_count 和 importance_score"""
        try:
            length_score = (len(user_input) // 20) * 0.1
            keyword_score = sum(
                1 for keyword in self.emotion_detector.emotion_dictionary.keys()
                for k in self.emotion_detector.emotion_dictionary[keyword]["keywords"]
                if k.lower() in user_input.lower()
            ) * 0.3
            intensity_score = emotion_analysis["intensity"]
            importance_score = length_score + keyword_score + intensity_score

            embedding_response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=f"{user_input} {bot_response}"
            )
            embedding = embedding_response.data[0].embedding
            
            existing = self.supabase.table(self.memories_table)\
                .select("id", "access_count")\
                .eq("conversation_id", conversation_id)\
                .eq("user_message", user_input)\
                .eq("memory_type", "conversation")\
                .execute()
            
            access_count = existing.data[0]["access_count"] + 1 if existing.data else 1
            
            data = {
                "conversation_id": conversation_id,
                "user_message": user_input,
                "assistant_message": bot_response,
                "embedding": embedding,
                "memory_type": "conversation",
                "platform": "Web",
                "document_content": f"對話記錄: {user_input} -> {bot_response}",
                "created_at": datetime.now().isoformat(),
                "access_count": access_count,
                "importance_score": importance_score,
                "file_name": file_name,
                "ai_id": ai_id,
                "message_type": "text"
            }
            
            if existing.data:
                self.supabase.table(self.memories_table)\
                    .update(data)\
                    .eq("id", existing.data[0]["id"])\
                    .execute()
            else:
                self.supabase.table(self.memories_table).insert(data).execute()
            
            print(f"✅ 記憶已儲存/更新 - 用戶: {conversation_id[:8]}..., access_count: {access_count}, importance_score: {importance_score:.2f}")
            
        except Exception as e:
            print(f"❌ 儲存記憶失敗：{e}")

    def get_conversation_history(self, conversation_id: str, limit: int = 10):
        """獲取對話歷史"""
        try:
            result = self.supabase.table(self.memories_table)\
                .select("user_message, assistant_messagesage, created_at")\
                .eq("conversation_id", conversation_id)\
                .eq("memory_type", "conversation")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            if result.data:
                history = []
                for msg in reversed(result.data):
                    history.append(f"用戶: {msg['user_message']}")
                    history.append(f"小宸光: {msg['assistant_messagesage']}")
                return "\n".join(history)
            return ""
            
        except Exception as e:
            print(f"❌ 獲取歷史失敗：{e}")
            return ""

    async def search_relevant_memories(self, conversation_id: str, query: str, limit: int = 3):
        """搜尋相關記憶"""
        try:
            embedding_response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_embedding = embedding_response.data[0].embedding
            
            result = self.supabase.rpc('match_memories', {
                'query_embedding': query_embedding,
                'match_count': limit,
                'conversation_id': conversation_id
            }).execute()
            
            if result.data:
                memories = []
                for memory in result.data:
                    memories.append(f"相關記憶: {memory['user_message']} -> {memory['assistant_message']}")
                return "\n".join(memories)
            return ""
            
        except Exception as e:
            print(f"❌ 搜尋記憶失敗：{e}")
            return await self.traditional_search(conversation_id, query, limit)

    async def traditional_search(self, conversation_id: str, query: str, limit: int = 3):
        """傳統文字搜尋（備用方案）"""
        try:
            result = self.supabase.table(self.memories_table)\
                .select("user_message, assistant_message")\
                .eq("conversation_id", conversation_id)\
                .eq("memory_type", "conversation")\
                .limit(limit * 2)\
                .execute()
            
            if result.data:
                relevant = []
                query_words = query.lower().split()
                
                for memory in result.data:
                    user_msg = memory['user_message'].lower()
                    if any(word in user_msg for word in query_words):
                        relevant.append(f"相關記憶: {memory['user_message']} -> {memory['assistant_messagesage']}")
                        if len(relevant) >= limit:
                            break
                
                return "\n".join(relevant)
            return ""
        except Exception as e:
            print(f"❌ 傳統搜尋失敗：{e}")
            return ""

    async def recall_memories(self, user_message: str, conversation_id: str) -> str:
        """根據使用者輸入，從記憶資料庫中召回相關對話記憶"""
        try:
            raw_memories = await self.search_relevant_memories(conversation_id, user_message, limit=3)
            
            if not raw_memories:
                recent_result = self.supabase.table(self.memories_table)\
                    .select("user_message, assistant_message")\
                    .eq("conversation_id", conversation_id)\
                    .eq("memory_type", "conversation")\
                    .order("created_at", desc=True)\
                    .limit(5)\
                    .execute()
                if recent_result.data:
                    raw_memories = "\n".join([f"相關記憶: {m['user_message']} -> {m['assistant_messagesage']}" for m in recent_result.data])
            
            if not raw_memories:
                return ""
            
            memory_lines = raw_memories.split("\n")
            formatted_memories = ["【喚醒記憶】"]
            for line in memory_lines:
                if line.startswith("相關記憶:"):
                    parts = line.replace("相關記憶: ", "").split(" -> ")
                    if len(parts) == 2:
                        user_msg, assistant_msg = parts
                        formatted_memories.append(f"- 你曾對我說：「{user_msg}」")
                        formatted_memories.append(f"- 我當時回應你：「{assistant_msg}」")
            
            return "\n".join(formatted_memories) if len(formatted_memories) > 1 else ""
            
        except Exception as e:
            print(f"❌ 記憶召回失敗：{e}")
            return ""

    async def save_emotional_state(self, user_id: str, emotion_analysis: dict, context: str = ""):
        """儲存情緒狀態到 emotional_states 表格"""
        try:
            data = {
                "user_id": user_id,
                "emotion_type": emotion_analysis["dominant_emotion"],
                "intensity": emotion_analysis["intensity"],
                "context": context,
                "timestamp": datetime.now().isoformat()
            }
            
            self.supabase.table("emotional_states").insert(data).execute()
            print(f"✅ 情緒狀態已儲存 - 用戶: {user_id[:8]}...")
            
        except Exception as e:
            print(f"❌ 儲存情緒狀態失敗：{e}")
