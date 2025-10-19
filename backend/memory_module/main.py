"""
記憶模組 - Memory Module
負責短期記憶（Redis）、長期記憶（Supabase）與 Token 化處理
"""
from typing import Dict, Any, Optional, List
from backend.base_module import BaseModule
from backend.redis_mock import get_redis_client
from backend.supabase_handler import get_supabase
import json
from datetime import datetime

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("⚠️ tiktoken 未安裝，Token 化功能將被停用")


class MemoryModule(BaseModule):
    """記憶模組類別"""
    
    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_name, config)
        self.redis_client = None
        self.supabase_client = None
        self.tokenizer = None
        self.redis_ttl = self.config.get("settings", {}).get("redis_ttl", 86400)
    
    async def load(self) -> bool:
        """載入模組"""
        try:
            self.log_info("正在載入記憶模組...")
            
            # 初始化 Redis Mock
            self.redis_client = get_redis_client()
            
            # 初始化 Supabase
            self.supabase_client = get_supabase()
            
            # 初始化 Tokenizer
            if TIKTOKEN_AVAILABLE:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
                self.log_info("✅ Tokenizer 已初始化")
            else:
                self.log_warning("⚠️ Tokenizer 未可用，將使用字元數估算")
            
            self._initialized = True
            self.log_info("✅ 記憶模組載入完成")
            return True
            
        except Exception as e:
            self.log_error(f"載入失敗: {e}")
            return False
    
    async def unload(self) -> bool:
        """卸載模組"""
        try:
            self.log_info("正在卸載記憶模組...")
            self._initialized = False
            return True
        except Exception as e:
            self.log_error(f"卸載失敗: {e}")
            return False
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理記憶相關操作
        
        支援操作：
        - store_conversation: 儲存對話
        - retrieve_memory: 召回記憶
        - tokenize_text: 文字 Token 化
        """
        operation = data.get("operation")
        
        if operation == "store_conversation":
            return await self._store_conversation(data)
        elif operation == "retrieve_memory":
            return await self._retrieve_memory(data)
        elif operation == "tokenize_text":
            return await self._tokenize_text(data)
        else:
            return {"error": f"未知操作: {operation}"}
    
    async def _store_conversation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """儲存對話到 Redis 和 Supabase"""
        try:
            conversation_id = data.get("conversation_id")
            user_message = data.get("user_message")
            assistant_message = data.get("assistant_message")
            reflection = data.get("reflection", "")
            
            # Token 化
            tokens_data = await self._tokenize_conversation(user_message, assistant_message)
            
            # 儲存到 Redis（短期記憶）
            redis_key = f"conv:{conversation_id}:latest"
            redis_value = json.dumps({
                "user_msg": user_message,
                "assistant_msg": assistant_message,
                "reflection": reflection,
                "tokens_data": tokens_data,
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False)
            
            self.redis_client.set(redis_key, redis_value, ex=self.redis_ttl)
            
            return {
                "success": True,
                "redis_key": redis_key,
                "tokens_data": tokens_data,
                "message": "對話已儲存至記憶系統"
            }
            
        except Exception as e:
            self.log_error(f"儲存對話失敗: {e}")
            return {"success": False, "error": str(e)}
    
    async def _retrieve_memory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """從 Redis 召回最近的記憶"""
        try:
            conversation_id = data.get("conversation_id")
            redis_key = f"conv:{conversation_id}:latest"
            
            value = self.redis_client.get(redis_key)
            if value:
                memory_data = json.loads(value)
                return {"success": True, "memory": memory_data}
            else:
                return {"success": False, "message": "無記憶資料"}
                
        except Exception as e:
            self.log_error(f"召回記憶失敗: {e}")
            return {"success": False, "error": str(e)}
    
    async def _tokenize_text(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """將文字進行 Token 化"""
        try:
            text = data.get("text", "")
            tokens_data = await self._tokenize_conversation(text, "")
            return {"success": True, "tokens_data": tokens_data}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _tokenize_conversation(self, user_msg: str, assistant_msg: str) -> Dict[str, List[int]]:
        """Token 化對話內容"""
        if not TIKTOKEN_AVAILABLE or not self.tokenizer:
            # 使用字元數估算
            return {
                "user_tokens": list(range(len(user_msg))),
                "assistant_tokens": list(range(len(assistant_msg))),
                "total_count": len(user_msg) + len(assistant_msg),
                "method": "char_estimate"
            }
        
        try:
            user_tokens = self.tokenizer.encode(user_msg)
            assistant_tokens = self.tokenizer.encode(assistant_msg)
            
            return {
                "user_tokens": user_tokens,
                "assistant_tokens": assistant_tokens,
                "total_count": len(user_tokens) + len(assistant_tokens),
                "method": "tiktoken"
            }
        except Exception as e:
            self.log_error(f"Token 化失敗: {e}")
            return {
                "user_tokens": [],
                "assistant_tokens": [],
                "total_count": 0,
                "error": str(e)
            }
