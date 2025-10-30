"""
記憶核心 - Memory Core
AI 數字宇宙的中樞神經資料層核心控制器

負責協調：
1. Token 化處理
2. Redis 短期記憶
3. Supabase 長期記憶
4. IPFS 索引（預留）
5. 模組間通信
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from .tokenizer import TokenizerEngine
from .redis_interface import RedisInterface
from .supabase_interface import SupabaseInterface
from .io_contract import validate_and_normalize, create_memory_record
from backend.modules.ipfs_handler import get_ipfs_handler

class MemoryCore:
    """記憶核心控制器"""
    
    def __init__(
        self, 
        config: Optional[Dict[str, Any]] = None,
        redis_client=None,
        supabase_client=None
    ):
        """
        初始化記憶核心
        
        參數:
            config: 模組配置
            redis_client: Redis 客戶端
            supabase_client: Supabase 客戶端
        """
        self.config = config or {}
        
        print("🧠 正在初始化記憶核心...")
        
        self.tokenizer = TokenizerEngine(
            tokenizer_name=self.config.get("tokenizer_name")
        )
        
        self.redis = RedisInterface(redis_client=redis_client)
        
        self.supabase = SupabaseInterface(
            supabase_client=supabase_client,
            config=self.config
        )
        
        # IPFS 處理器（用於生成 CID）
        self.ipfs = get_ipfs_handler()
        
        print("✅ 記憶核心初始化完成（含 IPFS CID 生成）")
    
    def save_chat(
        self, 
        user_message: str, 
        assistant_message: str, 
        conversation_id: str, 
        user_id: str,
        reflection: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        儲存對話內容（短期 + 長期）
        
        參數:
            user_message: 使用者訊息
            assistant_message: AI 回覆
            conversation_id: 對話 ID
            user_id: 使用者 ID
            reflection: 反思結果（可選）
        
        返回:
            儲存結果
        """
        try:
            token_data = self.tokenizer.pack_token_record(
                user=user_message,
                assistant=assistant_message,
                reflection_json=reflection
            )
            
            # 生成對話的 CID（內容識別符）
            cid = self.ipfs.generate_conversation_cid(
                user_message=user_message,
                assistant_message=assistant_message,
                timestamp=datetime.utcnow().isoformat()
            )
            
            memory_record = create_memory_record(
                conversation_id=conversation_id,
                user_id=user_id,
                user_message=user_message,
                assistant_message=assistant_message,
                reflection=reflection,
                token_data=token_data,
                cid=cid
            )
            
            redis_data = {
                "user_msg": user_message,
                "assistant_msg": assistant_message,
                "reflection": reflection,
                "token_data": token_data,
                "user_id": user_id,
                "timestamp": int(datetime.utcnow().timestamp())
            }
            
            redis_success = self.redis.store_short_term(
                conversation_id, 
                redis_data
            )
            
            # ⚡ 即時對話只存 Redis（提升速度，降低資料庫負擔）
            # 💾 長期儲存使用 flush_redis_to_supabase() 批次刷寫
            # supabase_success = self.supabase.store_single_memory(memory_record)
            
            return {
                "success": True,
                "redis_stored": redis_success,
                "supabase_stored": False,  # 改為批次寫入模式
                "token_count": token_data.get("total_count", 0),
                "conversation_id": conversation_id,
                "cid": cid,
                "note": "即時對話已存入 Redis，使用 flush_redis_to_supabase() 批次寫入長期儲存"
            }
            
        except Exception as e:
            print(f"❌ 儲存對話失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def save_reflection(
        self, 
        reflection_text: str, 
        conversation_id: str,
        user_id: str,
        feedback_loop_id: Optional[str] = None,
        upload_to_ipfs: bool = False
    ) -> Dict[str, Any]:
        """
        儲存反思紀錄
        
        參數:
            reflection_text: 反思內容
            conversation_id: 對話 ID
            user_id: 使用者 ID
            feedback_loop_id: 反饋循環 ID
            upload_to_ipfs: 是否上傳到 IPFS
        
        返回:
            儲存結果
        """
        try:
            if isinstance(reflection_text, dict):
                reflection_data = reflection_text
                reflection_text_str = json.dumps(reflection_text, ensure_ascii=False)
            else:
                reflection_data = {"summary": reflection_text}
                reflection_text_str = reflection_text
            
            token_data = self.tokenizer.pack_token_record(
                reflection_json=reflection_data
            )
            
            cid = None
            if upload_to_ipfs:
                cid = self.upload_to_ipfs(reflection_text_str)
            
            reflection_record = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "reflection": reflection_data,
                "token_data": token_data,
                "cid": cid,
                "feedback_loop_id": feedback_loop_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            reflection_id = self.supabase.store_reflection(reflection_record)
            
            return {
                "success": True,
                "reflection_id": reflection_id,
                "cid": cid,
                "token_count": token_data.get("total_count", 0)
            }
            
        except Exception as e:
            print(f"❌ 儲存反思失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def store_conversation(
        self,
        conversation_id: str,
        user_id: str,
        user_msg: Optional[str] = None,
        assistant_msg: Optional[str] = None,
        reflection: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        統一儲存介面（用於路由調用）
        
        參數:
            conversation_id: 對話 ID
            user_id: 使用者 ID
            user_msg: 使用者訊息
            assistant_msg: AI 回覆
            reflection: 反思結果
        
        返回:
            儲存結果
        """
        if user_msg and assistant_msg:
            return self.save_chat(
                user_message=user_msg,
                assistant_message=assistant_msg,
                conversation_id=conversation_id,
                user_id=user_id,
                reflection=reflection
            )
        else:
            return {
                "success": False,
                "error": "缺少必要的訊息內容"
            }
    
    def load_recent_context(
        self, 
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        讀取最近的對話上下文
        
        參數:
            conversation_id: 對話 ID
        
        返回:
            上下文資料或 None
        """
        redis_context = self.redis.load_recent_context(conversation_id)
        
        if redis_context:
            return redis_context
        
        supabase_memories = self.supabase.get_conversation_memories(
            conversation_id, 
            limit=1
        )
        
        if supabase_memories and len(supabase_memories) > 0:
            latest = supabase_memories[0]
            return {
                "user_msg": latest.get("user_message"),
                "assistant_msg": latest.get("assistant_message"),
                "reflection": latest.get("reflection"),
                "token_data": latest.get("token_data"),
                "user_id": latest.get("user_id"),
                "ts": latest.get("created_at")
            }
        
        return None
    
    def get_memory_context(
        self, 
        conversation_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        獲取完整的對話記憶上下文
        
        參數:
            conversation_id: 對話 ID
            limit: 最大返回數量
        
        返回:
            記憶上下文列表
        """
        redis_history = self.redis.get_conversation_history(conversation_id, limit)
        
        if redis_history:
            return redis_history
        
        return self.supabase.get_conversation_memories(conversation_id, limit)
    
    def get_reflection_cid(
        self, 
        conversation_id: str
    ) -> Optional[str]:
        """
        獲取反思的 IPFS CID
        
        參數:
            conversation_id: 對話 ID
        
        返回:
            CID 或 None
        """
        reflections = self.supabase.get_user_reflections(conversation_id, limit=1)
        
        if reflections and len(reflections) > 0:
            return reflections[0].get("cid")
        
        return None
    
    def upload_to_ipfs(self, content: str) -> Optional[str]:
        """
        上傳內容到 IPFS（預留功能）
        
        參數:
            content: 內容
        
        返回:
            CID 或 None
        """
        print("⚠️ IPFS 功能尚未實現，將在未來版本中啟用")
        return None
    
    def persist_long_term(
        self, 
        records: List[Dict[str, Any]]
    ) -> int:
        """
        批次持久化到長期記憶
        
        參數:
            records: 記錄列表
        
        返回:
            成功寫入的筆數
        """
        return self.supabase.commit_to_longterm(records)
    
    def flush_redis_to_supabase(
        self, 
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        將 Redis 待刷寫隊列批次寫入 Supabase
        
        參數:
            batch_size: 批次大小
        
        返回:
            刷寫結果
        """
        try:
            pending_records = self.redis.get_pending_records(batch_size)
            
            if not pending_records:
                return {
                    "success": True,
                    "flushed_count": 0,
                    "message": "沒有待刷寫記錄"
                }
            
            records_to_persist = []
            for item in pending_records:
                conversation_id = item.get("conversation_id")
                data = item.get("data", {})
                
                record = create_memory_record(
                    conversation_id=conversation_id,
                    user_id=data.get("user_id"),
                    user_message=data.get("user_msg"),
                    assistant_message=data.get("assistant_msg"),
                    reflection=data.get("reflection"),
                    token_data=data.get("token_data")
                )
                
                records_to_persist.append(record)
            
            success_count = self.persist_long_term(records_to_persist)
            
            return {
                "success": True,
                "total_pending": len(pending_records),
                "flushed_count": success_count,
                "failed_count": len(pending_records) - success_count
            }
            
        except Exception as e:
            print(f"❌ 刷寫失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        返回:
            健康狀態
        """
        return {
            "status": "healthy",
            "tokenizer": {
                "method": "tiktoken" if not self.tokenizer.fallback_mode else "utf8_bytes",
                "encoding": self.tokenizer.tokenizer_name
            },
            "redis": self.redis.get_stats(),
            "supabase": self.supabase.get_stats()
        }
