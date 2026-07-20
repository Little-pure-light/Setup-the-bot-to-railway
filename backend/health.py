"""
Liveness / Readiness 健康檢查（不消耗 OpenAI Token、不回傳 Secret）
"""
from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import urlparse

APP_VERSION = os.getenv("APP_VERSION", "1.0.1")


def liveness_payload() -> Dict[str, Any]:
    """程序存活即可，不依賴外部服務。"""
    return {
        "status": "ok",
        "check": "liveness",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _env_configured(name: str) -> bool:
    v = (os.getenv(name) or "").strip()
    return bool(v)


def readiness_payload() -> Dict[str, Any]:
    """
    就緒檢查：環境變數是否設定 + 可選 DNS/連線探測。
    不呼叫 OpenAI API（不消耗 token）。
    """
    services: Dict[str, str] = {
        "app": "ok",
        "openai_config": "configured" if _env_configured("OPENAI_API_KEY") else "missing",
        "supabase_config": "configured"
        if _env_configured("SUPABASE_URL")
        and (_env_configured("SUPABASE_ANON_KEY") or _env_configured("SUPABASE_KEY"))
        else "missing",
        "redis": "not_configured",
        "supabase": "unknown",
    }

    # Redis：只檢查是否設定 URL，不強制連線成功
    if _env_configured("REDIS_URL") or _env_configured("REDIS_HOST"):
        services["redis"] = "configured"
    else:
        services["redis"] = "unavailable"

    # Supabase：僅 DNS 解析，不帶 key、不查表
    sb_url = (os.getenv("SUPABASE_URL") or "").strip()
    if sb_url:
        try:
            host = urlparse(sb_url).hostname
            if host:
                if host.endswith(".local") or host == "mock.supabase.local":
                    services["supabase"] = "mock"
                else:
                    socket.getaddrinfo(host, 443)
                    services["supabase"] = "ok"
            else:
                services["supabase"] = "invalid_url"
        except OSError:
            services["supabase"] = "dns_failed"
        except Exception:
            services["supabase"] = "error"
    else:
        services["supabase"] = "missing_url"

    critical_missing = [
        k
        for k, v in {
            "openai_config": services["openai_config"],
            "supabase_config": services["supabase_config"],
        }.items()
        if v == "missing"
    ]

    if critical_missing:
        status = "not_ready"
    elif services["supabase"] in ("dns_failed", "error", "invalid_url"):
        status = "degraded"
    elif services["redis"] == "unavailable":
        status = "degraded"  # Redis 可選降級
    else:
        status = "ok"

    return {
        "status": status,
        "check": "readiness",
        "version": APP_VERSION,
        "services": services,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # 明確不包含任何 secret
    }
