"""記憶體版 Redis 介面 mock。"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional


class MockRedisClient:
    def __init__(self):
        self.store: Dict[str, str] = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None):
        self.store[key] = value
        return True

    def setex(self, key: str, time: int, value: str):
        self.store[key] = value
        return True

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    def keys(self, pattern: str = "*"):
        # 極簡 glob：只支援 prefix*
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self.store if k.startswith(prefix)]
        return [k for k in self.store if k == pattern]

    def exists(self, key: str):
        return 1 if key in self.store else 0


class MockRedisInterface:
    """對齊 backend.redis_interface 常用方法的子集。"""

    def __init__(self):
        self.redis = MockRedisClient()

    def store_short_term(self, conversation_id: str, payload: dict):
        key = f"conv:{conversation_id}:latest"
        self.redis.set(key, json.dumps(payload, ensure_ascii=False))

    def load_recent_context(self, conversation_id: str) -> Optional[dict]:
        raw = self.redis.get(f"conv:{conversation_id}:latest")
        if not raw:
            return None
        return json.loads(raw)
