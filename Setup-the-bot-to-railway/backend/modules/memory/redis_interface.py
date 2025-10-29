"""
Redis 短期記憶接口 - Redis Short-term Memory Interface
負責快速存取最近對話與反思資料
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import os


class RedisInterface:
    """Redis 短期記憶接口類"""

    def __init__(self, redis_client=None):
        """
        初始化 Redis 接口
        
        參數:
            redis_client: Redis 客戶端（如為 None 則使用 redis_mock）
        """
        self.redis = redis_client
        self.ttl_seconds = int(os.getenv("MEMORY_REDIS_TTL_SECONDS",
                                         "86400"))  # 預設 24 小時

        # 如果沒有傳入 redis_client，嘗試自動初始化
        if self.redis is None:
            self._auto_init_redis()

    def _auto_init_redis(self):
        """
        自動初始化 Redis（優先真實連接，降級到 Mock）
        支援格式：
        - REDIS_ENDPOINT + REDIS_TOKEN (Upstash 格式，支援 SSL)
        - REDIS_URL (標準格式)
        - Redis Mock (降級方案)
        """
        # 方案 1：使用 REDIS_URL（最優先，支援完整 URL 格式）
        redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_ENDPOINT")

        if redis_url:
            try:
                import redis

                # 自動修正：Upstash 需要 SSL，將 redis:// 改成 rediss://
                if redis_url.startswith("redis://"):
                    redis_url = redis_url.replace("redis://", "rediss://", 1)
                    print(f"🔧 [AUTO-FIX] 啟用 SSL：redis:// → rediss://")

                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                print(f"✅ Redis 已連接（URL 模式）")
                return
            except Exception as e:
                print(f"⚠️ Redis URL 連接失敗: {type(e).__name__}: {e}")
                print(f"⚠️ 嘗試其他方案...")

        # 方案 2：使用 REDIS_ENDPOINT + REDIS_TOKEN（分離格式，僅用於純 hostname）
        redis_endpoint = os.getenv("REDIS_ENDPOINT")
        redis_token = os.getenv("REDIS_TOKEN")

        # 確保不是 URL 格式（已在方案 1 處理）
        if redis_endpoint and redis_token and not redis_endpoint.startswith(
            ('redis://', 'rediss://')):
            try:
                import redis
                self.redis = redis.Redis(host=redis_endpoint.strip(),
                                         port=6379,
                                         password=redis_token,
                                         ssl=True,
                                         ssl_cert_reqs=None,
                                         decode_responses=True)
                self.redis.ping()
                print(f"✅ Redis 已連接（Endpoint + Token 模式）: {redis_endpoint}")
                return
            except Exception as e:
                print(f"⚠️ Redis Endpoint+Token 連接失敗: {type(e).__name__}: {e}")
                print(f"⚠️ 降級到 Mock 模式...")

        # 方案 3：使用標準 REDIS_URL（再次檢查，防止重複）
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                print(f"✅ Redis 已連接（URL 模式）")
                return
            except Exception as e:
                print(f"⚠️ Redis URL 連接失敗: {e}，降級到 Mock 模式...")

        # 方案 3：降級到 Redis Mock
        self._init_redis_mock()

    def _init_redis_mock(self):
        """初始化 Redis Mock（用於開發環境）"""
        try:
            from backend.redis_mock import RedisMock
            self.redis = RedisMock()
            print("✅ Redis Interface 使用 Mock 模式")
        except ImportError:
            print("❌ 無法載入 Redis Mock，短期記憶功能將無法使用")
            self.redis = None

    def store_short_term(self, conversation_id: str, data: Dict[str,
                                                                Any]) -> bool:
        """
        儲存短期記憶到 Redis
        
        參數:
            conversation_id: 對話 ID
            data: 記憶資料
        
        返回:
            是否成功
        """
        if not self.redis:
            return False

        try:
            key = self._get_conversation_key(conversation_id)
            value = json.dumps(data, ensure_ascii=False)

            self.redis.set(key, value)
            self.redis.expire(key, self.ttl_seconds)

            self._append_to_pending_queue(conversation_id, data)

            return True
        except Exception as e:
            print(f"❌ Redis 儲存失敗: {e}")
            return False

    def load_recent_context(self,
                            conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        從 Redis 載入最近的對話上下文
        
        參數:
            conversation_id: 對話 ID
        
        返回:
            記憶資料或 None
        """
        if not self.redis:
            return None

        try:
            key = self._get_conversation_key(conversation_id)
            value = self.redis.get(key)

            if value:
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                return json.loads(value)

            return None
        except Exception as e:
            print(f"❌ Redis 讀取失敗: {e}")
            return None

    def get_conversation_history(self,
                                 conversation_id: str,
                                 limit: int = 10) -> List[Dict[str, Any]]:
        """
        獲取對話歷史（從 Redis 或 pending queue）
        
        參數:
            conversation_id: 對話 ID
            limit: 最大返回數量
        
        返回:
            對話歷史列表
        """
        if not self.redis:
            return []

        try:
            queue_key = f"pending:queue:{conversation_id}"
            items = self.redis.lrange(queue_key, 0, limit - 1)

            history = []
            for item in items:
                if isinstance(item, bytes):
                    item = item.decode('utf-8')
                history.append(json.loads(item))

            return history
        except Exception as e:
            print(f"❌ 獲取對話歷史失敗: {e}")
            return []

    def _append_to_pending_queue(self, conversation_id: str, data: Dict[str,
                                                                        Any]):
        """
        將資料加入待刷寫隊列
        
        參數:
            conversation_id: 對話 ID
            data: 記憶資料
        """
        try:
            queue_key = "pending:flush:queue"
            pending_item = {
                "conversation_id": conversation_id,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }

            self.redis.rpush(queue_key,
                             json.dumps(pending_item, ensure_ascii=False))

            conv_queue_key = f"pending:queue:{conversation_id}"
            self.redis.rpush(conv_queue_key,
                             json.dumps(data, ensure_ascii=False))
            self.redis.expire(conv_queue_key, self.ttl_seconds)

        except Exception as e:
            print(f"⚠️ 加入待刷寫隊列失敗: {e}")

    def get_pending_records(self,
                            batch_size: int = 100) -> List[Dict[str, Any]]:
        """
        獲取待刷寫的記錄
        
        參數:
            batch_size: 批次大小
        
        返回:
            待刷寫記錄列表
        """
        if not self.redis:
            return []

        try:
            queue_key = "pending:flush:queue"
            items = []

            for _ in range(batch_size):
                item = self.redis.lpop(queue_key)
                if not item:
                    break

                if isinstance(item, bytes):
                    item = item.decode('utf-8')
                items.append(json.loads(item))

            return items
        except Exception as e:
            print(f"❌ 獲取待刷寫記錄失敗: {e}")
            return []

    def clear_conversation(self, conversation_id: str) -> bool:
        """
        清除指定對話的短期記憶
        
        參數:
            conversation_id: 對話 ID
        
        返回:
            是否成功
        """
        if not self.redis:
            return False

        try:
            key = self._get_conversation_key(conversation_id)
            self.redis.delete(key)

            queue_key = f"pending:queue:{conversation_id}"
            self.redis.delete(queue_key)

            return True
        except Exception as e:
            print(f"❌ 清除對話記憶失敗: {e}")
            return False

    def _get_conversation_key(self, conversation_id: str) -> str:
        """
        獲取對話的 Redis key
        
        參數:
            conversation_id: 對話 ID
        
        返回:
            Redis key
        """
        return f"conv:{conversation_id}:latest"

    def get_stats(self) -> Dict[str, Any]:
        """
        獲取 Redis 統計資訊
        
        返回:
            統計資訊
        """
        if not self.redis:
            return {"status": "unavailable"}

        try:
            queue_key = "pending:flush:queue"
            queue_length = self.redis.llen(queue_key) if hasattr(
                self.redis, 'llen') else 0

            return {
                "status": "active",
                "pending_queue_length": queue_length,
                "ttl_seconds": self.ttl_seconds
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
