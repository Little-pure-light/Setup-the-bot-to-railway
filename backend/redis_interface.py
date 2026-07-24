"""
Redis 短期記憶接口

用途：
- 最新對話快取 conv:{id}:latest
- 上傳檔案暫存 upload:{conversation_id}:*
- 反思快取（由 ReflectionStorage 使用）
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import os


class RedisInterface:
    """Redis 短期記憶接口"""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.ttl_seconds = int(os.getenv("MEMORY_REDIS_TTL_SECONDS", "86400"))

        if self.redis is None:
            self._auto_init_redis()

    def _auto_init_redis(self):
        """優先真實 Redis，失敗則降級 Mock"""
        redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_ENDPOINT")

        if redis_url:
            try:
                import redis

                if redis_url.startswith("redis://"):
                    redis_url = redis_url.replace("redis://", "rediss://", 1)
                    print("🔧 [AUTO-FIX] 啟用 SSL：redis:// → rediss://")

                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                print("✅ Redis 已連接（URL 模式）")
                return
            except Exception as e:
                print(f"⚠️ Redis URL 連接失敗: {type(e).__name__}: {e}")

        redis_endpoint = os.getenv("REDIS_ENDPOINT")
        redis_token = os.getenv("REDIS_TOKEN")

        if redis_endpoint and redis_token and not redis_endpoint.startswith(
            ("redis://", "rediss://")
        ):
            try:
                import redis
                self.redis = redis.Redis(
                    host=redis_endpoint.strip(),
                    port=6379,
                    password=redis_token,
                    ssl=True,
                    ssl_cert_reqs=None,
                    decode_responses=True,
                )
                self.redis.ping()
                print(f"✅ Redis 已連接（Endpoint + Token）: {redis_endpoint}")
                return
            except Exception as e:
                print(f"⚠️ Redis Endpoint+Token 連接失敗: {type(e).__name__}: {e}")

        self._init_redis_mock()

    def _init_redis_mock(self):
        try:
            from backend.redis_mock import RedisMock
            self.redis = RedisMock()
            print("✅ Redis Interface 使用 Mock 模式")
        except ImportError:
            print("❌ 無法載入 Redis Mock，短期記憶功能將無法使用")
            self.redis = None

    def store_short_term(self, conversation_id: str, data: Dict[str, Any]) -> bool:
        """
        Store latest conversation snapshot under conv:{id}:latest only.

        Canonical payload (Infrastructure Phase):
          messages: list[{role, content}]
          summary: str
          reflection: unified reflection contract dict | null
          updated_at: ISO8601
        Legacy keys (user_msg/assistant_msg) are still accepted on write and
        normalized into the canonical shape for backward compatibility.
        """
        if not self.redis:
            return False
        try:
            payload = self.normalize_latest_payload(data)
            key = self._get_conversation_key(conversation_id)
            self.redis.set(key, json.dumps(payload, ensure_ascii=False))
            self.redis.expire(key, self.ttl_seconds)
            return True
        except Exception as e:
            print(f"❌ Redis 儲存失敗: {e}")
            return False

    def load_recent_context(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        try:
            key = self._get_conversation_key(conversation_id)
            value = self.redis.get(key)
            if not value:
                return None
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            raw = json.loads(value)
            return self.normalize_latest_payload(raw)
        except Exception as e:
            print(f"❌ Redis 讀取失敗: {e}")
            return None

    @staticmethod
    def normalize_latest_payload(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize legacy and canonical Redis conversation payloads."""
        from datetime import datetime, timezone

        data = dict(data or {})
        messages = data.get("messages")
        if not isinstance(messages, list):
            messages = []
            # legacy flat fields
            user_msg = data.get("user_msg") or data.get("user_message") or data.get("user_input")
            asst_msg = (
                data.get("assistant_msg")
                or data.get("assistant_message")
                or data.get("bot_response")
            )
            if user_msg:
                messages.append({"role": "user", "content": str(user_msg)})
            if asst_msg:
                messages.append({"role": "assistant", "content": str(asst_msg)})

        # keep legacy mirrors for older readers
        user_mirror = ""
        asst_mirror = ""
        for m in messages:
            if not isinstance(m, dict):
                continue
            if m.get("role") == "user" and not user_mirror:
                user_mirror = str(m.get("content") or "")
            if m.get("role") == "assistant" and not asst_mirror:
                asst_mirror = str(m.get("content") or "")

        reflection = data.get("reflection")
        if reflection is not None:
            try:
                from backend.modules.reflection_contract import normalize_reflection

                reflection = normalize_reflection(reflection)
            except Exception:
                pass

        summary = data.get("summary")
        if not summary:
            # derive short summary from last assistant or user line
            summary = (asst_mirror or user_mirror or "")[:200]

        updated_at = data.get("updated_at") or data.get("timestamp")
        if not updated_at:
            updated_at = datetime.now(timezone.utc).isoformat()
        elif isinstance(updated_at, (int, float)):
            updated_at = datetime.fromtimestamp(
                float(updated_at), tz=timezone.utc
            ).isoformat()

        payload = {
            "messages": messages,
            "summary": str(summary or ""),
            "reflection": reflection,
            "updated_at": str(updated_at),
            # legacy compatibility mirrors
            "user_msg": user_mirror or data.get("user_msg") or "",
            "assistant_msg": asst_mirror or data.get("assistant_msg") or "",
            "user_id": data.get("user_id"),
            "timestamp": data.get("timestamp") or updated_at,
        }
        # optional token accounting (never inside message text)
        if data.get("token_usage"):
            payload["token_usage"] = data["token_usage"]
        return payload

    def clear_conversation(self, conversation_id: str) -> bool:
        if not self.redis:
            return False
        try:
            self.redis.delete(self._get_conversation_key(conversation_id))
            return True
        except Exception as e:
            print(f"❌ 清除對話記憶失敗: {e}")
            return False

    def _get_conversation_key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}:latest"

    def get_stats(self) -> Dict[str, Any]:
        if not self.redis:
            return {"status": "unavailable"}
        try:
            return {
                "status": "active",
                "ttl_seconds": self.ttl_seconds,
                "mode": type(self.redis).__name__,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
