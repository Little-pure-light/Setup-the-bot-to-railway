"""
Copilot Memory Integration
整合小宸光記憶系統，提供給 Copilot 使用
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
import sys
import os

project_root = os.path.join(os.path.dirname(__file__), '../../..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.openai_handler import get_openai_client
from config import config

logger = logging.getLogger("copilot_memory")

class CopilotMemoryIntegration:
    """Copilot 記憶整合類別"""
    
    def __init__(self, redis_interface, supabase_client):
        self.redis = redis_interface
        self.supabase = supabase_client
        self.openai_client = get_openai_client()
    
    async def get_recent_memories(
        self,
        conversation_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        從共用資料庫取得最近的記憶
        
        參數:
            conversation_id: 對話 ID（可選）
            limit: 返回數量
        
        返回:
            記憶列表
        """
        try:
            query = self.supabase.table(config.SUPABASE_MEMORIES_TABLE).select("*")
            
            if conversation_id:
                query = query.eq("conversation_id", conversation_id)
            
            response = query.order("created_at", desc=True).limit(limit).execute()
            
            memories = response.data if response.data else []
            logger.info(f"📥 取得 {len(memories)} 筆記憶")
            
            return memories
            
        except Exception as e:
            logger.error(f"❌ 取得記憶失敗: {e}")
            return []
    
    async def get_personality_traits(self) -> Dict:
        """
        取得最新的人格特質
        
        返回:
            人格特質字典
        """
        try:
            response = self.supabase.table(config.SUPABASE_PERSONALITY_TABLE).select(
                "*"
            ).order("created_at", desc=True).limit(1).execute()
            
            if response.data:
                personality = response.data[0]
                logger.info(f"🌈 取得人格特質: {personality.get('trait', 'default')}")
                return personality
            
            return {"trait": "analytical", "description": "預設分析型人格"}
            
        except Exception as e:
            logger.error(f"❌ 取得人格特質失敗: {e}")
            return {"trait": "default", "description": "預設人格"}
    
    def build_enhanced_prompt(
        self,
        user_prompt: str,
        recent_memories: List[Dict],
        personality: Dict,
        file_name: Optional[str] = None,
        file_context: Optional[str] = None
    ) -> str:
        """
        組合增強的 prompt，包含記憶上下文與人格
        
        參數:
            user_prompt: 用戶原始提示
            recent_memories: 最近記憶
            personality: 人格特質
            file_name: 檔案名稱
            file_context: 檔案上下文
        
        返回:
            增強後的 prompt
        """
        
        # 建構記憶上下文
        memory_context = ""
        if recent_memories:
            memory_context = "### 相關歷史記憶\n"
            for i, mem in enumerate(recent_memories[:3], 1):
                user_msg = mem.get("user_message", "")[:100]
                assistant_msg = mem.get("assistant_message", "")[:100]
                memory_context += f"{i}. 用戶: {user_msg}\n   助手: {assistant_msg}\n\n"
        
        # 建構人格指引
        personality_guide = f"""### 人格特質
當前人格: {personality.get('trait', 'analytical')}
描述: {personality.get('description', '專業且友善的助手')}
"""
        
        # 建構檔案上下文
        file_section = ""
        if file_name or file_context:
            file_section = "### 檔案上下文\n"
            if file_name:
                file_section += f"檔案名稱: {file_name}\n"
            if file_context:
                file_section += f"內容摘要: {file_context[:500]}\n"
            file_section += "\n"
        
        # 組合完整 prompt
        enhanced_prompt = f"""
{personality_guide}

{memory_context}

{file_section}

### 用戶請求
{user_prompt}

請根據以上記憶與人格特質，提供專業且友善的回應。
"""
        
        return enhanced_prompt
    
    async def simulate_copilot_response(self, enhanced_prompt: str) -> str:
        """
        模擬 Copilot 回覆（未來替換為真實 Copilot API）
        
        參數:
            enhanced_prompt: 增強後的 prompt
        
        返回:
            模擬回覆
        """
        try:
            # 使用 OpenAI API 模擬 Copilot 回覆
            response = self.openai_client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一個專業的程式設計助手，像 GitHub Copilot 一樣提供程式碼建議和技術指導。"
                    },
                    {
                        "role": "user",
                        "content": enhanced_prompt
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            reply = response.choices[0].message.content
            logger.info(f"🤖 模擬 Copilot 回覆已生成")
            
            return reply
            
        except Exception as e:
            logger.error(f"❌ 生成回覆失敗: {e}")
            return "抱歉，目前無法生成回覆。請稍後再試。"
    
    async def save_copilot_memory(
        self,
        conversation_id: str,
        user_id: str,
        session_id: str,
        user_prompt: str,
        copilot_reply: str,
        file_name: Optional[str] = None
    ) -> str:
        """
        儲存 Copilot 對話到共用記憶資料庫
        
        參數:
            conversation_id: 對話 ID
            user_id: 用戶 ID
            session_id: Session ID
            user_prompt: 用戶提示
            copilot_reply: Copilot 回覆
            file_name: 檔案名稱
        
        返回:
            記憶 ID
        """
        try:
            memory_data = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "user_message": user_prompt,
                "assistant_message": copilot_reply,
                "file_name": file_name,
                "memory_type": config.COPILOT_MEMORY_TYPE,
                "platform": config.COPILOT_PLATFORM,
                "ai_id": config.COPILOT_AI_ID,
                "session_id": session_id,
                "source": "copilot_agent",
                "created_at": datetime.utcnow().isoformat(),
                "importance_score": 0.7,
                "access_count": 0
            }
            
            response = self.supabase.table(config.SUPABASE_MEMORIES_TABLE).insert(
                memory_data
            ).execute()
            
            if response.data:
                memory_id = response.data[0].get("id")
                logger.info(f"💾 記憶已儲存 | ID: {memory_id}")
                return str(memory_id)
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ 儲存記憶失敗: {e}")
            raise
    
    async def generate_and_save_reflection(
        self,
        conversation_id: str,
        user_id: str,
        session_id: str,
        user_prompt: str,
        copilot_reply: str,
        memory_id: Optional[str] = None
    ) -> Dict:
        """
        生成反思摘要並儲存到共用資料庫
        
        參數:
            conversation_id: 對話 ID
            user_id: 用戶 ID
            session_id: Session ID
            user_prompt: 用戶提示
            copilot_reply: Copilot 回覆
            memory_id: 對應的記憶 ID
        
        返回:
            反思資料
        """
        try:
            # 生成反思內容
            reflection_prompt = f"""
分析以下對話，生成簡潔的反思摘要：

用戶問題: {user_prompt}
助手回覆: {copilot_reply}

請提供：
1. 這次對話的關鍵洞察
2. 可改進的地方
3. 相關技術標籤

以 JSON 格式回覆：
{{
  "insight": "關鍵洞察",
  "improvement": "改進建議",
  "tags": ["tag1", "tag2"]
}}
"""
            
            response = self.openai_client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "你是一個專業的反思分析師。"},
                    {"role": "user", "content": reflection_prompt}
                ],
                max_tokens=200,
                temperature=0.5
            )
            
            reflection_text = response.choices[0].message.content
            
            # 嘗試解析 JSON
            try:
                reflection_data = json.loads(reflection_text)
            except:
                reflection_data = {
                    "insight": reflection_text,
                    "improvement": "",
                    "tags": []
                }
            
            # 儲存到資料庫
            reflection_record = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "reflection_content": reflection_data.get("insight", ""),
                "confidence_score": 0.8,
                "analysis_tags": json.dumps(reflection_data.get("tags", [])),
                "copilot_snapshot_id": session_id,
                "related_message_id": memory_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            supabase_response = self.supabase.table(
                config.SUPABASE_REFLECTIONS_TABLE
            ).insert(reflection_record).execute()
            
            logger.info(f"💭 反思已儲存")
            
            return {
                "content": reflection_data.get("insight", ""),
                "confidence": 0.8,
                "tags": reflection_data.get("tags", [])
            }
            
        except Exception as e:
            logger.error(f"❌ 生成反思失敗: {e}")
            return {
                "content": "反思生成失敗",
                "confidence": 0.0,
                "tags": []
            }
    
    async def save_session_status(
        self,
        session_id: str,
        status: str,
        file_name: Optional[str] = None
    ):
        """
        儲存 session 狀態到 Redis
        
        參數:
            session_id: Session ID
            status: 狀態（processing/completed/failed）
            file_name: 檔案名稱
        """
        try:
            redis_key = f"copilot:session:{session_id}"
            session_data = {
                "status": status,
                "file_name": file_name,
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.redis.redis.setex(
                redis_key,
                config.SESSION_TTL,
                json.dumps(session_data, ensure_ascii=False)
            )
            
            logger.info(f"📊 Session 狀態已儲存: {session_id} -> {status}")
            
        except Exception as e:
            logger.error(f"❌ 儲存 session 狀態失敗: {e}")
    
    async def get_session_status(self, session_id: str) -> Optional[Dict]:
        """
        從 Redis 取得 session 狀態
        
        參數:
            session_id: Session ID
        
        返回:
            Session 資料
        """
        try:
            redis_key = f"copilot:session:{session_id}"
            data = self.redis.redis.get(redis_key)
            
            if data:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 取得 session 狀態失敗: {e}")
            return None
