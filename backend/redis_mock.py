"""
Redis 記憶體模擬接口
提供與 Redis 類似的緩存功能，日後可直接替換為 Upstash Redis
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import threading

class RedisMock:
    """模擬 Redis 緩存接口"""
    
    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """設置鍵值對，可選擇過期時間（秒）"""
        with self._lock:
            expire_at = None
            if ex:
                expire_at = datetime.now() + timedelta(seconds=ex)
            
            self._storage[key] = {
                "value": value,
                "expire_at": expire_at,
                "created_at": datetime.now()
            }
            return True
    
    def get(self, key: str) -> Optional[str]:
        """獲取鍵值"""
        with self._lock:
            if key not in self._storage:
                return None
            
            item = self._storage[key]
            
            # 檢查是否過期
            if item["expire_at"] and datetime.now() > item["expire_at"]:
                del self._storage[key]
                return None
            
            return item["value"]
    
    def delete(self, key: str) -> int:
        """刪除鍵"""
        with self._lock:
            if key in self._storage:
                del self._storage[key]
                return 1
            return 0
    
    def exists(self, key: str) -> int:
        """檢查鍵是否存在"""
        value = self.get(key)
        return 1 if value is not None else 0
    
    def hset(self, name: str, key: str, value: str) -> int:
        """設置 Hash 欄位"""
        with self._lock:
            if name not in self._storage:
                self._storage[name] = {"value": {}, "expire_at": None, "created_at": datetime.now()}
            
            if not isinstance(self._storage[name]["value"], dict):
                self._storage[name]["value"] = {}
            
            self._storage[name]["value"][key] = value
            return 1
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """獲取 Hash 欄位"""
        with self._lock:
            if name not in self._storage:
                return None
            
            item = self._storage[name]
            if item["expire_at"] and datetime.now() > item["expire_at"]:
                del self._storage[name]
                return None
            
            if not isinstance(item["value"], dict):
                return None
            
            return item["value"].get(key)
    
    def hgetall(self, name: str) -> Dict[str, str]:
        """獲取所有 Hash 欄位"""
        with self._lock:
            if name not in self._storage:
                return {}
            
            item = self._storage[name]
            if item["expire_at"] and datetime.now() > item["expire_at"]:
                del self._storage[name]
                return {}
            
            if not isinstance(item["value"], dict):
                return {}
            
            return item["value"].copy()
    
    def expire(self, key: str, seconds: int) -> int:
        """設置鍵的過期時間"""
        with self._lock:
            if key not in self._storage:
                return 0
            
            self._storage[key]["expire_at"] = datetime.now() + timedelta(seconds=seconds)
            return 1
    
    def ttl(self, key: str) -> int:
        """獲取鍵的剩餘生存時間（秒）"""
        with self._lock:
            if key not in self._storage:
                return -2
            
            item = self._storage[key]
            if not item["expire_at"]:
                return -1
            
            remaining = (item["expire_at"] - datetime.now()).total_seconds()
            return int(remaining) if remaining > 0 else -2
    
    def keys(self, pattern: str = "*") -> list:
        """獲取符合模式的所有鍵"""
        with self._lock:
            if pattern == "*":
                return list(self._storage.keys())
            
            # 簡單的模式匹配
            import re
            regex_pattern = pattern.replace("*", ".*")
            return [key for key in self._storage.keys() if re.match(regex_pattern, key)]
    
    def flushall(self) -> bool:
        """清空所有數據"""
        with self._lock:
            self._storage.clear()
            return True


# 全局單例
_redis_mock_instance: Optional[RedisMock] = None

def get_redis_client() -> RedisMock:
    """獲取 Redis Mock 客戶端（單例模式）"""
    global _redis_mock_instance
    if _redis_mock_instance is None:
        _redis_mock_instance = RedisMock()
        print("✅ Redis Mock 已初始化（記憶體模式）")
    return _redis_mock_instance
