"""
反思儲存服務 - Reflection Storage Service
實現三層儲存架構：
1. Redis 快取層：最新 5 筆反思（24小時 TTL）
2. Supabase 永久儲存層：完整反思記錄
3. Pinecone 向量層：反思語義向量（用於相似度檢索）
"""
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class ReflectionStorage:
    """反思儲存服務類"""
    
    def __init__(self, redis_interface=None, supabase_client=None, pinecone_handler=None):
        """
        初始化反思儲存服務
        
        參數:
            redis_interface: Redis 接口實例
            supabase_client: Supabase 客戶端
            pinecone_handler: Pinecone 處理器實例
        """
        self.redis = redis_interface
        self.supabase = supabase_client
        self.pinecone = pinecone_handler
        
        self.reflections_table = os.getenv("SUPABASE_REFLECTIONS_TABLE", "xiaochenguang_reflections")
        self.redis_max_items = 5
        self.redis_ttl = 86400
        
        print(f"✅ 反思儲存服務已初始化")
        print(f"   - Redis 快取: {'啟用' if self.redis else '停用'}")
        print(f"   - Supabase 永久儲存: {'啟用' if self.supabase else '停用'}")
        print(f"   - Pinecone 向量儲存: {'啟用' if self.pinecone else '停用'}")
    
    async def store_reflection(
        self,
        reflection_data: Dict[str, Any],
        conversation_id: str,
        user_id: str = "default_user",
        related_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        儲存反思到三層架構
        
        參數:
            reflection_data: 反思資料（來自 reflection_module）
            conversation_id: 對話 ID
            user_id: 使用者 ID
            related_message_id: 關聯的訊息 ID
        
        返回:
            儲存結果
        """
        reflection_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        storage_record = {
            "id": reflection_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "related_message_id": related_message_id,
            "reflection_content": reflection_data.get("summary", ""),
            "analysis_tags": {
                "dominant_causes": reflection_data.get("causes", [])[:3],
                "top_improvements": reflection_data.get("improvements", [])[:3],
                "meta_analysis": reflection_data.get("meta_analysis", {})
            },
            "reflection_level": {
                "observation": reflection_data.get("observation", {}),
                "causes": reflection_data.get("causes", []),
                "improvements": reflection_data.get("improvements", [])
            },
            "confidence_score": reflection_data.get("confidence", 0.0),
            "created_at": timestamp
        }
        
        results = {
            "reflection_id": reflection_id,
            "timestamp": timestamp,
            "redis_success": False,
            "supabase_success": False,
            "pinecone_success": False
        }
        
        redis_success = await self._store_to_redis(storage_record, conversation_id)
        results["redis_success"] = redis_success
        
        supabase_success = await self._store_to_supabase(storage_record)
        results["supabase_success"] = supabase_success
        
        pinecone_success = await self._store_to_pinecone(storage_record)
        results["pinecone_success"] = pinecone_success
        
        success_count = sum([redis_success, supabase_success, pinecone_success])
        results["overall_success"] = success_count >= 2
        
        print(f"📊 反思儲存結果: Redis={redis_success}, Supabase={supabase_success}, Pinecone={pinecone_success}")
        
        return results
    
    async def _store_to_redis(self, record: Dict[str, Any], conversation_id: str) -> bool:
        """儲存到 Redis 快取（僅保留最新 5 筆）"""
        if not self.redis:
            return False
        
        try:
            redis_key = f"reflections:{conversation_id}"
            
            existing = self.redis.redis.lrange(redis_key, 0, -1) if hasattr(self.redis.redis, 'lrange') else []
            
            simplified_record = {
                "id": record["id"],
                "summary": record["reflection_content"],
                "confidence": record["confidence_score"],
                "timestamp": record["created_at"]
            }
            
            self.redis.redis.lpush(redis_key, json.dumps(simplified_record, ensure_ascii=False))
            
            self.redis.redis.ltrim(redis_key, 0, self.redis_max_items - 1)
            
            self.redis.redis.expire(redis_key, self.redis_ttl)
            
            print(f"✅ 反思已儲存到 Redis: {redis_key}")
            return True
            
        except Exception as e:
            print(f"❌ Redis 儲存失敗: {type(e).__name__}: {e}")
            return False
    
    async def _store_to_supabase(self, record: Dict[str, Any]) -> bool:
        """儲存到 Supabase 永久儲存"""
        if not self.supabase:
            return False
        
        try:
            supabase_record = {
                "id": record["id"],
                "created_at": record["created_at"],
                "conversation_id": record["conversation_id"],
                "user_id": record["user_id"],
                "related_message_id": record.get("related_message_id"),
                "reflection_content": record["reflection_content"],
                "analysis_tags": record["analysis_tags"],
                "reflection_level": record["reflection_level"],
                "confidence_score": record["confidence_score"]
            }
            
            response = self.supabase.table(self.reflections_table).insert(supabase_record).execute()
            
            if response.data:
                print(f"✅ 反思已儲存到 Supabase: {record['id']}")
                return True
            else:
                print(f"⚠️ Supabase 返回空數據")
                return False
                
        except Exception as e:
            print(f"❌ Supabase 儲存失敗: {type(e).__name__}: {e}")
            return False
    
    async def _store_to_pinecone(self, record: Dict[str, Any]) -> bool:
        """儲存到 Pinecone 向量資料庫"""
        if not self.pinecone:
            return False
        
        try:
            reflection_text = record["reflection_content"]
            
            metadata = {
                "conversation_id": record["conversation_id"],
                "user_id": record["user_id"],
                "timestamp": record["created_at"],
                "confidence": record["confidence_score"],
                "summary": reflection_text[:500]
            }
            
            success = self.pinecone.store_reflection_with_text(
                reflection_id=record["id"],
                reflection_text=reflection_text,
                metadata=metadata
            )
            
            return success
            
        except Exception as e:
            print(f"❌ Pinecone 儲存失敗: {type(e).__name__}: {e}")
            return False
    
    async def get_latest_reflections(
        self,
        conversation_id: str,
        limit: int = 5,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        獲取最新反思（優先從 Redis 讀取，降級到 Supabase）
        
        參數:
            conversation_id: 對話 ID
            limit: 最大返回數量
            use_cache: 是否使用 Redis 快取
        
        返回:
            反思列表
        """
        if use_cache and self.redis:
            redis_reflections = await self._get_from_redis(conversation_id, limit)
            if redis_reflections:
                print(f"✅ 從 Redis 獲取 {len(redis_reflections)} 筆反思")
                return redis_reflections
        
        if self.supabase:
            supabase_reflections = await self._get_from_supabase(conversation_id, limit)
            if supabase_reflections:
                print(f"✅ 從 Supabase 獲取 {len(supabase_reflections)} 筆反思")
                return supabase_reflections
        
        return []
    
    async def _get_from_redis(self, conversation_id: str, limit: int) -> List[Dict[str, Any]]:
        """從 Redis 獲取反思"""
        if not self.redis:
            return []
        
        try:
            redis_key = f"reflections:{conversation_id}"
            items = self.redis.redis.lrange(redis_key, 0, limit - 1)
            
            reflections = []
            for item in items:
                if isinstance(item, bytes):
                    item = item.decode('utf-8')
                reflections.append(json.loads(item))
            
            return reflections
            
        except Exception as e:
            print(f"❌ Redis 讀取失敗: {e}")
            return []
    
    async def _get_from_supabase(self, conversation_id: str, limit: int) -> List[Dict[str, Any]]:
        """從 Supabase 獲取反思"""
        if not self.supabase:
            return []
        
        try:
            response = self.supabase.table(self.reflections_table)\
                .select("*")\
                .eq("conversation_id", conversation_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            if response.data:
                return response.data
            return []
            
        except Exception as e:
            print(f"❌ Supabase 讀取失敗: {e}")
            return []
    
    async def search_similar_reflections(
        self,
        query_text: str,
        top_k: int = 5,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜尋相似的反思（使用 Pinecone 向量檢索）
        
        參數:
            query_text: 查詢文本
            top_k: 返回前 K 個結果
            user_id: 可選的使用者 ID 過濾
        
        返回:
            相似反思列表
        """
        if not self.pinecone:
            print("⚠️ Pinecone 未啟用，無法執行向量搜尋")
            return []
        
        try:
            query_embedding = self.pinecone.generate_embedding(query_text)
            
            if not query_embedding:
                return []
            
            filter_metadata = {"user_id": user_id} if user_id else None
            
            similar = self.pinecone.query_similar_reflections(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_metadata=filter_metadata
            )
            
            return similar
            
        except Exception as e:
            print(f"❌ 向量搜尋失敗: {e}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """獲取儲存統計資訊"""
        stats = {
            "redis": self.redis.get_stats() if self.redis else {"status": "disabled"},
            "pinecone": self.pinecone.get_stats() if self.pinecone else {"status": "disabled"},
            "supabase": {
                "status": "active" if self.supabase else "disabled",
                "table": self.reflections_table
            }
        }
        
        return stats
