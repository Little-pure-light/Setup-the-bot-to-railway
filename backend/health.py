"""
Liveness / Readiness 健康檢查（不消耗 OpenAI Token、不回傳 Secret）

## 檢查深度說明（審核修正）

### Liveness (`/live`)
- 只確認進程可回應。
- 不檢查 Supabase / Redis / OpenAI。

### Readiness (`/ready`)
- **OpenAI**：只檢查 `OPENAI_API_KEY` 是否已設定（configured / missing），
  **不會**呼叫 OpenAI API，不消耗 token。
- **Supabase**：
  - `supabase_config`：URL + key 環境變數是否存在。
  - `supabase`：預設 **只做設定狀態**（configured / missing_url / mock），
    **不做**資料庫查詢、**不做** RPC、**不驗證**資料可讀寫。
  - 可選 `READY_CHECK_SUPABASE_DNS=true` 時才做 DNS（於執行緒池，避免阻塞 event loop）；
    DNS 成功僅代表主機名可解析，**不代表** DB 可用。
- **Redis**：只檢查 `REDIS_URL` / `REDIS_HOST` 是否設定
  （configured / unavailable），**不** PING Redis。

因此：`/ready` 的 `ok` **不得**解讀為「資料庫已完整可用」；
正式驗收仍需聊天 Smoke 與記憶讀寫驗證。
"""
from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

APP_VERSION = os.getenv("APP_VERSION", "1.0.1")


def _git_commit() -> Optional[str]:
    """可選部署 commit（Railway / 自訂），截短且永不含 secret。"""
    raw = (
        os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or ""
    ).strip()
    if not raw:
        return None
    # 只允許 hex-ish commit，避免把亂填的 secret 回傳
    safe = "".join(c for c in raw if c.isalnum())[:40]
    return safe or None


def _version_fields() -> Dict[str, Any]:
    data: Dict[str, Any] = {"version": APP_VERSION}
    commit = _git_commit()
    if commit:
        data["git_commit"] = commit
    return data


def liveness_payload() -> Dict[str, Any]:
    """程序存活即可，不依賴外部服務。"""
    return {
        "status": "ok",
        "check": "liveness",
        **_version_fields(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _env_configured(name: str) -> bool:
    v = (os.getenv(name) or "").strip()
    return bool(v)


def _supabase_dns_status(host: str) -> str:
    """同步 DNS（僅在明確啟用或經 to_thread 呼叫時使用）。"""
    try:
        socket.getaddrinfo(host, 443)
        return "dns_ok"
    except OSError:
        return "dns_failed"
    except Exception:
        return "dns_error"


def readiness_payload(*, check_dns: Optional[bool] = None) -> Dict[str, Any]:
    """
    就緒檢查（設定層級為主）。

    check_dns:
      None → 讀取 READY_CHECK_SUPABASE_DNS（預設 false，高頻 /ready 不阻塞）
      True/False → 強制
    """
    if check_dns is None:
        check_dns = os.getenv("READY_CHECK_SUPABASE_DNS", "false").lower() in (
            "1",
            "true",
            "yes",
        )

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

    # Redis：僅設定檢查，不連線
    if _env_configured("REDIS_URL") or _env_configured("REDIS_HOST"):
        services["redis"] = "configured"
    else:
        services["redis"] = "unavailable"

    # Supabase：預設僅設定；可選 DNS（非 DB 可用性）
    sb_url = (os.getenv("SUPABASE_URL") or "").strip()
    if sb_url:
        host = urlparse(sb_url).hostname
        if not host:
            services["supabase"] = "invalid_url"
        elif host.endswith(".local") or host == "mock.supabase.local":
            services["supabase"] = "mock"
        elif check_dns:
            services["supabase"] = _supabase_dns_status(host)
        else:
            # 有 URL 即標示 config_only（非「DB 健康」）
            services["supabase"] = "config_only"
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
    elif services["supabase"] in ("dns_failed", "dns_error", "invalid_url"):
        status = "degraded"
    elif services["redis"] == "unavailable":
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "check": "readiness",
        **_version_fields(),
        "services": services,
        "notes": {
            "supabase": "config_and_optional_dns_only_not_db_probe",
            "redis": "env_presence_only_not_ping",
            "openai": "key_presence_only_no_api_call",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def readiness_payload_async() -> Dict[str, Any]:
    """
    非同步就緒檢查：若啟用 DNS，於 asyncio.to_thread 執行，避免阻塞 event loop。
    """
    import asyncio

    check_dns = os.getenv("READY_CHECK_SUPABASE_DNS", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    if not check_dns:
        return readiness_payload(check_dns=False)

    # 先組設定狀態，DNS 部分丟執行緒
    base = readiness_payload(check_dns=False)
    sb_url = (os.getenv("SUPABASE_URL") or "").strip()
    host = urlparse(sb_url).hostname if sb_url else None
    if host and not host.endswith(".local") and host != "mock.supabase.local":
        dns_status = await asyncio.to_thread(_supabase_dns_status, host)
        base["services"]["supabase"] = dns_status
        if dns_status in ("dns_failed", "dns_error"):
            base["status"] = "degraded"
        elif base["status"] != "not_ready":
            # dns_ok + 其餘正常 → ok（仍非 DB 探測）
            if base["services"].get("redis") == "unavailable":
                base["status"] = "degraded"
            else:
                base["status"] = "ok"
    return base
