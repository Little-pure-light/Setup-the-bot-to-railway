"""
Redis 短期記憶接口（Railway-safe）

- 不強制 redis:// → rediss://（由 URL scheme 或 REDIS_SSL 決定）
- 明確 connect/read timeout，避免長阻塞
- 單一共用 client（get_shared_redis_interface）
- 模式：real | mock | none
- 日誌只記狀態與錯誤類型，不記密鑰／完整 URL
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("redis_interface")

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_shared_interface: Optional["RedisInterface"] = None
_redis_mode: str = "none"  # real | mock | none
_last_error_type: Optional[str] = None
_last_error_msg: str = ""
_last_reconnect_attempt: float = 0.0


def _reconnect_cooldown_seconds() -> float:
    try:
        return max(5.0, float(os.getenv("REDIS_RECONNECT_COOLDOWN_SECONDS", "45")))
    except (TypeError, ValueError):
        return 45.0


def get_redis_mode() -> str:
    return _redis_mode


def get_redis_last_error() -> Dict[str, str]:
    return {
        "error_type": _last_error_type or "",
        "error_class": _last_error_msg or "",
    }


def _mask_url(url: str) -> str:
    """Log-safe host only."""
    try:
        p = urlparse(url)
        host = p.hostname or "unknown"
        scheme = p.scheme or "?"
        port = f":{p.port}" if p.port else ""
        return f"{scheme}://***@{host}{port}"
    except Exception:
        return "(unparseable)"


def _timeouts() -> Tuple[float, float]:
    connect = float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "2.0"))
    read = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "2.0"))
    return max(0.2, connect), max(0.2, read)


def _want_ssl(url: str) -> bool:
    """TLS only when scheme is rediss:// or REDIS_SSL explicitly true."""
    flag = (os.getenv("REDIS_SSL") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    return url.strip().lower().startswith("rediss://")


def _scan_keys(client, match: str, count: int = 100) -> List[str]:
    """Prefer SCAN over KEYS to avoid blocking large keyspaces."""
    if client is None:
        return []
    # Mock may implement keys() only
    if hasattr(client, "scan") and callable(getattr(client, "scan")):
        try:
            cursor = 0
            found: List[str] = []
            while True:
                cursor, batch = client.scan(cursor=cursor, match=match, count=count)
                if batch:
                    found.extend(
                        b.decode("utf-8") if isinstance(b, bytes) else str(b)
                        for b in batch
                    )
                if cursor == 0 or cursor == "0":
                    break
                try:
                    cursor = int(cursor)
                except (TypeError, ValueError):
                    break
            return found
        except Exception as e:
            logger.warning("redis_scan_failed type=%s", type(e).__name__)
    if hasattr(client, "keys"):
        try:
            raw = client.keys(match)
            return [
                k.decode("utf-8") if isinstance(k, bytes) else str(k) for k in (raw or [])
            ]
        except Exception as e:
            logger.warning("redis_keys_fallback_failed type=%s", type(e).__name__)
    return []


def create_redis_client() -> Tuple[Any, str, Optional[str]]:
    """
    Create underlying redis client.
    Returns (client, mode, error_type).
    mode: real | mock | none
    """
    global _last_error_type, _last_error_msg
    connect_t, socket_t = _timeouts()
    redis_url = (os.getenv("REDIS_URL") or "").strip()
    # REDIS_ENDPOINT as full URL also accepted
    endpoint_as_url = (os.getenv("REDIS_ENDPOINT") or "").strip()
    if not redis_url and endpoint_as_url.startswith(("redis://", "rediss://")):
        redis_url = endpoint_as_url

    if redis_url:
        try:
            import redis

            # Do NOT rewrite redis:// → rediss://
            kwargs = {
                "decode_responses": True,
                "socket_connect_timeout": connect_t,
                "socket_timeout": socket_t,
                "retry_on_timeout": False,
            }
            # redis-py from_url respects scheme; optional health_check
            client = redis.from_url(redis_url, **kwargs)
            client.ping()
            _last_error_type = None
            _last_error_msg = ""
            logger.info(
                "redis_connected mode=real via=url target=%s",
                _mask_url(redis_url),
            )
            print(f"✅ Redis real connected (url) target={_mask_url(redis_url)}")
            return client, "real", None
        except Exception as e:
            _last_error_type = type(e).__name__
            _last_error_msg = type(e).__name__
            logger.warning(
                "redis_url_connect_failed type=%s target=%s",
                type(e).__name__,
                _mask_url(redis_url),
            )
            print(f"⚠️ Redis URL connect failed type={type(e).__name__}")

    redis_endpoint = (os.getenv("REDIS_ENDPOINT") or "").strip()
    redis_token = (os.getenv("REDIS_TOKEN") or "").strip()
    redis_host = (os.getenv("REDIS_HOST") or "").strip()
    host = redis_host or (
        redis_endpoint
        if redis_endpoint and not redis_endpoint.startswith(("redis://", "rediss://"))
        else ""
    )
    port = int(os.getenv("REDIS_PORT", "6379") or 6379)

    if host and redis_token:
        try:
            import redis

            use_ssl = _want_ssl(os.getenv("REDIS_URL") or "") or (
                (os.getenv("REDIS_SSL") or "true").lower()
                in ("1", "true", "yes", "on")
            )
            # host+token often Upstash → default SSL true unless REDIS_SSL=false
            if (os.getenv("REDIS_SSL") or "").strip().lower() in (
                "0",
                "false",
                "no",
                "off",
            ):
                use_ssl = False
            elif not (os.getenv("REDIS_SSL") or "").strip():
                # default for token/host: SSL on (Upstash-style)
                use_ssl = True

            client = redis.Redis(
                host=host,
                port=port,
                password=redis_token,
                ssl=use_ssl,
                ssl_cert_reqs=None if use_ssl else None,
                decode_responses=True,
                socket_connect_timeout=connect_t,
                socket_timeout=socket_t,
                retry_on_timeout=False,
            )
            client.ping()
            _last_error_type = None
            _last_error_msg = ""
            logger.info(
                "redis_connected mode=real via=host host=%s ssl=%s",
                host,
                use_ssl,
            )
            print(f"✅ Redis real connected (host) host={host} ssl={use_ssl}")
            return client, "real", None
        except Exception as e:
            _last_error_type = type(e).__name__
            _last_error_msg = type(e).__name__
            logger.warning(
                "redis_host_connect_failed type=%s host=%s",
                type(e).__name__,
                host,
            )
            print(f"⚠️ Redis host connect failed type={type(e).__name__}")

    # Mock fallback (keep capability; never pretend real)
    try:
        from backend.redis_mock import RedisMock

        client = RedisMock()
        _last_error_type = _last_error_type  # keep prior connect error if any
        logger.info(
            "redis_mode=mock reason=%s",
            _last_error_type or "not_configured",
        )
        print(
            f"✅ Redis mock mode reason={_last_error_type or 'not_configured'}"
        )
        return client, "mock", _last_error_type
    except ImportError:
        _last_error_type = "MockImportError"
        logger.error("redis_mode=none mock_unavailable")
        print("❌ Redis unavailable (no mock)")
        return None, "none", "MockImportError"


def get_shared_redis_interface(*, force_refresh: bool = False) -> "RedisInterface":
    """
    Process-wide singleton RedisInterface.

    Critical: force_refresh reconnects **in-place** on the same object so
    module-level holders (chat_router.redis_interface, MemorySystem.redis, …)
    keep working after mock→real without swapping Python references.
    """
    global _shared_interface, _redis_mode
    with _lock:
        if _shared_interface is None:
            iface = RedisInterface(use_shared_init=True)
            _shared_interface = iface
            _redis_mode = iface.mode
            return iface
        if force_refresh:
            client, mode, _err = create_redis_client()
            _shared_interface.adopt_backend(client, mode)
            _redis_mode = mode
        return _shared_interface


def _has_redis_config() -> bool:
    return bool(
        (os.getenv("REDIS_URL") or "").strip()
        or (os.getenv("REDIS_HOST") or "").strip()
        or (
            (os.getenv("REDIS_ENDPOINT") or "").strip()
            and (os.getenv("REDIS_TOKEN") or "").strip()
        )
    )


def maybe_reconnect_redis(
    *, force: bool = False, allow_from_real: bool = False
) -> "RedisInterface":
    """
    Rate-limited reconnect that mutates the shared interface in-place.

    - mock/none + config → try real again
    - real + allow_from_real (ping failed) → try new connection (may become mock/real)
    Not invoked on every chat — /ready (and explicit health).
    """
    global _last_reconnect_attempt, _redis_mode
    iface = get_shared_redis_interface()
    if not _has_redis_config():
        return iface
    if iface.mode == "real" and not allow_from_real:
        return iface
    if iface.mode not in ("mock", "none", "real"):
        return iface

    now = time.time()
    with _lock:
        cooldown = _reconnect_cooldown_seconds()
        if not force and (now - _last_reconnect_attempt) < cooldown:
            return iface
        _last_reconnect_attempt = now

    prev = iface.mode
    logger.info(
        "redis_reconnect_attempt previous_mode=%s cooldown_s=%s force=%s allow_from_real=%s",
        prev,
        _reconnect_cooldown_seconds(),
        force,
        allow_from_real,
    )
    # In-place refresh (same object identity)
    client, mode, _err = create_redis_client()
    iface.adopt_backend(client, mode)
    _redis_mode = mode
    if mode == "real":
        logger.info("redis_reconnect_success mode=real previous=%s", prev)
        print(f"✅ Redis reconnected mode=real (was {prev})")
    else:
        logger.info(
            "redis_reconnect_not_real mode=%s err=%s previous=%s",
            mode,
            get_redis_last_error().get("error_type"),
            prev,
        )
    return iface


def redis_ping_status() -> Dict[str, Any]:
    """
    For /ready — short ping with classification.
    Returns status: not_configured | ping_ok | ping_fail | mock
    May attempt rate-limited reconnect when mock/configured or real disconnect.
    """
    has_config = _has_redis_config()
    if has_config:
        iface = maybe_reconnect_redis(force=False, allow_from_real=False)
    else:
        iface = get_shared_redis_interface()
    mode = iface.mode

    if mode == "mock":
        if not has_config:
            return {
                "status": "mock",
                "mode": "mock",
                "configured": False,
                "error_type": "",
            }
        return {
            "status": "mock",
            "mode": "mock",
            "configured": True,
            "error_type": get_redis_last_error().get("error_type") or "connect_failed",
            "reconnect_cooldown_s": _reconnect_cooldown_seconds(),
        }
    if mode == "none":
        return {
            "status": "not_configured" if not has_config else "ping_fail",
            "mode": "none",
            "configured": has_config,
            "error_type": get_redis_last_error().get("error_type") or "",
        }

    # real — verify ping; on failure try reconnect once (rate-limited)
    t0 = time.perf_counter()
    client = iface.get_client()
    try:
        if client is None:
            raise RuntimeError("NoClient")
        client.ping()
        ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status": "ping_ok",
            "mode": "real",
            "configured": True,
            "ping_ms": ms,
            "error_type": "",
        }
    except Exception as e:
        first_err = type(e).__name__
        # try recovery without waiting forever on ping_fail
        iface = maybe_reconnect_redis(force=False, allow_from_real=True)
        client2 = iface.get_client()
        t1 = time.perf_counter()
        try:
            if iface.mode == "real" and client2 is not None:
                client2.ping()
                return {
                    "status": "ping_ok",
                    "mode": "real",
                    "configured": True,
                    "ping_ms": int((time.perf_counter() - t1) * 1000),
                    "error_type": "",
                    "recovered_from": first_err,
                }
        except Exception as e2:
            return {
                "status": "ping_fail" if iface.mode == "real" else iface.mode,
                "mode": iface.mode,
                "configured": True,
                "error_type": type(e2).__name__,
                "previous_error_type": first_err,
                "ping_ms": int((time.perf_counter() - t0) * 1000),
            }
        return {
            "status": "ping_fail" if iface.mode == "real" else iface.mode,
            "mode": iface.mode,
            "configured": True,
            "error_type": first_err,
            "ping_ms": int((time.perf_counter() - t0) * 1000),
        }


class RedisInterface:
    """
    Redis 短期記憶接口.

    Shared singleton keeps object identity stable; adopt_backend() swaps the
    underlying client under a lock so chat_router / MemorySystem / ReflectionStorage
    module-level references keep using the live client after reconnect.
    """

    def __init__(
        self,
        redis_client=None,
        *,
        use_shared_init: bool = False,
        mode: Optional[str] = None,
    ):
        self.ttl_seconds = int(os.getenv("MEMORY_REDIS_TTL_SECONDS", "86400"))
        self._client_lock = threading.RLock()
        self.mode: str = "none"
        self.redis = redis_client
        if self.redis is not None:
            if mode in ("real", "mock", "none"):
                self.mode = mode
            else:
                name = type(self.redis).__name__
                self.mode = "mock" if name == "RedisMock" else "real"
            return
        client, mode_auto, _err = create_redis_client()
        self.redis = client
        self.mode = mode_auto

    def adopt_backend(self, client: Any, mode: str) -> None:
        """Thread-safe in-place client swap (preserves object identity)."""
        with self._client_lock:
            self.redis = client
            self.mode = mode if mode in ("real", "mock", "none") else "none"

    def get_client(self) -> Any:
        """Current underlying client (may change after adopt_backend)."""
        with self._client_lock:
            return self.redis

    def scan_keys(self, match: str, count: int = 100) -> List[str]:
        return _scan_keys(self.get_client(), match, count=count)

    def store_short_term(self, conversation_id: str, data: Dict[str, Any]) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            payload = self.normalize_latest_payload(data)
            key = self._get_conversation_key(conversation_id)
            client.set(key, json.dumps(payload, ensure_ascii=False))
            client.expire(key, self.ttl_seconds)
            return True
        except Exception as e:
            logger.warning("redis_store_failed type=%s", type(e).__name__)
            print(f"❌ Redis 儲存失敗 type={type(e).__name__}")
            return False

    def load_recent_context(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return None
        try:
            key = self._get_conversation_key(conversation_id)
            value = client.get(key)
            if not value:
                return None
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            raw = json.loads(value)
            return self.normalize_latest_payload(raw)
        except Exception as e:
            logger.warning("redis_load_failed type=%s", type(e).__name__)
            print(f"❌ Redis 讀取失敗 type={type(e).__name__}")
            return None

    @staticmethod
    def normalize_latest_payload(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        data = dict(data or {})
        messages = data.get("messages")
        if not isinstance(messages, list):
            messages = []
            user_msg = (
                data.get("user_msg")
                or data.get("user_message")
                or data.get("user_input")
            )
            asst_msg = (
                data.get("assistant_msg")
                or data.get("assistant_message")
                or data.get("bot_response")
            )
            if user_msg:
                messages.append({"role": "user", "content": str(user_msg)})
            if asst_msg:
                messages.append({"role": "assistant", "content": str(asst_msg)})

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
            "user_msg": user_mirror or data.get("user_msg") or "",
            "assistant_msg": asst_mirror or data.get("assistant_msg") or "",
            "user_id": data.get("user_id"),
            "timestamp": data.get("timestamp") or updated_at,
        }
        if data.get("token_usage"):
            payload["token_usage"] = data["token_usage"]
        return payload

    def clear_conversation(self, conversation_id: str) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            client.delete(self._get_conversation_key(conversation_id))
            return True
        except Exception as e:
            logger.warning("redis_clear_failed type=%s", type(e).__name__)
            print(f"❌ 清除對話記憶失敗 type={type(e).__name__}")
            return False

    def _get_conversation_key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}:latest"

    def get_stats(self) -> Dict[str, Any]:
        client = self.get_client()
        if not client:
            return {"status": "unavailable", "mode": self.mode or "none"}
        try:
            return {
                "status": "active",
                "ttl_seconds": self.ttl_seconds,
                "mode": self.mode,
                "client": type(client).__name__,
            }
        except Exception as e:
            return {"status": "error", "error_type": type(e).__name__, "mode": self.mode}
