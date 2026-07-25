#!/usr/bin/env python3
"""
§9 Memory V2 staging verification against a live backend.

Usage:
  set API_SECRET=...
  set BASE_URL=https://ai2.dreamground.net
  set NIGHT_GROWTH_INTERNAL_TOKEN=...   # optional; falls back to API_SECRET
  python scripts/verify_memory_v2_staging.py

Does not print secrets. Uses isolated staging_verify_* user ids.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

BASE = os.getenv("BASE_URL", "https://ai2.dreamground.net").rstrip("/")
API_SECRET = (os.getenv("API_SECRET") or os.getenv("NIGHT_GROWTH_INTERNAL_TOKEN") or "").strip()
NG_TOKEN = (os.getenv("NIGHT_GROWTH_INTERNAL_TOKEN") or API_SECRET).strip()
USER_A = os.getenv("VERIFY_USER_A", "staging_verify_a")
USER_B = os.getenv("VERIFY_USER_B", "staging_verify_b")
CONV_A = os.getenv("VERIFY_CONV_A", "staging_verify_conv_a")
CONV_B = os.getenv("VERIFY_CONV_B", "staging_verify_conv_b")


def _req(
    method: str,
    path: str,
    *,
    body: Optional[dict] = None,
    token: Optional[str] = None,
    timeout: float = 90.0,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Any, str]:
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.getcode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        code = e.code
    except Exception as e:
        return 0, None, str(e)
    try:
        parsed = json.loads(raw) if raw else None
    except Exception:
        parsed = raw
    return code, parsed, raw[:500]


def ok(name: str, passed: bool, detail: str = "") -> Dict[str, Any]:
    return {"name": name, "pass": passed, "detail": detail}


def main() -> int:
    results = []
    report: Dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "has_api_secret": bool(API_SECRET),
        "results": results,
    }

    # --- public health ---
    code, data, raw = _req("GET", "/health")
    gc = (data or {}).get("git_commit") if isinstance(data, dict) else None
    results.append(ok("health_liveness", code == 200 and (data or {}).get("status") == "ok", f"commit={gc}"))

    code, data, _ = _req("GET", "/ready")
    ready_status = (data or {}).get("status") if isinstance(data, dict) else None
    services = (data or {}).get("services") if isinstance(data, dict) else {}
    results.append(
        ok(
            "ready_endpoint",
            code == 200,
            f"status={ready_status} services={services}",
        )
    )
    redis_ok = (services or {}).get("redis") not in (None, "unavailable", "error")
    results.append(ok("redis_available", redis_ok, f"redis={ (services or {}).get('redis') }"))

    if not API_SECRET:
        results.append(ok("auth_token_present", False, "API_SECRET not set in environment"))
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["summary"] = {
            "passed": sum(1 for r in results if r["pass"]),
            "failed": sum(1 for r in results if not r["pass"]),
            "blocked": "Need API_SECRET to continue §9 authenticated tests",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    # --- auth surfaces ---
    code, data, _ = _req("GET", "/v1/models", token=API_SECRET)
    models = []
    if isinstance(data, dict):
        models = [m.get("id") for m in (data.get("data") or [])]
    results.append(ok("v1_models", code == 200 and "xiaochenguang" in models, f"code={code} models={models}"))

    # unauth should 401
    code_u, _, _ = _req("GET", "/v1/models")
    results.append(ok("v1_models_requires_auth", code_u == 401, f"code={code_u}"))

    # --- basic chat non-stream (field is user_message, not message) ---
    code, data, raw = _req(
        "POST",
        "/api/chat?stream=false",
        token=API_SECRET,
        body={
            "user_message": "驗證用：我的名字叫小測A，請用中文簡短回應。",
            "conversation_id": CONV_A,
            "user_id": USER_A,
        },
        timeout=120,
    )
    msg = (data or {}).get("assistant_message") if isinstance(data, dict) else None
    results.append(
        ok(
            "api_chat_non_stream",
            code == 200 and bool(msg),
            f"code={code} has_msg={bool(msg)} keys={list(data.keys()) if isinstance(data, dict) else type(data)}",
        )
    )

    # include_reflection status
    code, data, _ = _req(
        "POST",
        "/api/chat?stream=false&include_reflection=true",
        token=API_SECRET,
        body={
            "user_message": "再確認一次我的稱呼。",
            "conversation_id": CONV_A,
            "user_id": USER_A,
        },
        timeout=120,
    )
    rs = (data or {}).get("reflection_status") if isinstance(data, dict) else None
    results.append(
        ok(
            "reflection_status_field",
            code == 200 and rs in ("pending", "completed", "failed", "unavailable"),
            f"code={code} reflection_status={rs} has_reflection={bool((data or {}).get('reflection') if isinstance(data, dict) else None)}",
        )
    )

    # OpenAI compatible
    code, data, _ = _req(
        "POST",
        "/v1/chat/completions",
        token=API_SECRET,
        body={
            "model": "xiaochenguang",
            "stream": False,
            "messages": [{"role": "user", "content": "用一句話問好"}],
        },
        extra_headers={"X-Conversation-Id": CONV_A, "X-User-Id": USER_A},
        timeout=120,
    )
    content = None
    if isinstance(data, dict):
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            content = None
    results.append(ok("v1_chat_completions", code == 200 and bool(content), f"code={code}"))

    # --- Memory V2 dialogue matrix (spec 9.2) ---
    scenarios = [
        ("name", "我的名字是小測A，請記住這個稱呼。"),
        ("preference", "我偏好無糖綠茶，之後請記得。"),
        ("emotion", "我今天有點累，語氣請溫柔一點。"),
        ("knowledge", "請記住：專案代號是 LightSoul-Staging-Verify。"),
        ("recall_prior", "你還記得我的名字和飲料偏好嗎？請簡短回答。"),
        ("identity_q", "你是誰？請簡短自我介紹。"),
        ("growth", "如果我說你今天有成長，你會怎麼反思自己？"),
    ]
    for key, text in scenarios:
        code, data, _ = _req(
            "POST",
            "/api/chat?stream=false",
            token=API_SECRET,
            body={
                "user_message": text,
                "conversation_id": CONV_A,
                "user_id": USER_A,
            },
            timeout=120,
        )
        am = (data or {}).get("assistant_message") if isinstance(data, dict) else ""
        results.append(
            ok(
                f"scenario_{key}",
                code == 200 and bool(am),
                f"code={code} len={len(am or '')} snippet={(am or '')[:80]}",
            )
        )
        time.sleep(0.3)

    # continuity / recall check
    code, data, _ = _req(
        "POST",
        "/api/chat?stream=false",
        token=API_SECRET,
        body={
            "user_message": "上次我說過的專案代號是什麼？我的飲料偏好？",
            "conversation_id": CONV_A,
            "user_id": USER_A,
        },
        timeout=120,
    )
    am = ((data or {}).get("assistant_message") or "") if isinstance(data, dict) else ""
    hit = ("LightSoul" in am) or ("綠茶" in am) or ("小測" in am)
    results.append(ok("conversation_continuity_recall", code == 200 and hit, f"code={code} snippet={am[:120]}"))

    # isolation user B should not know A's secrets from B conversation
    code, data, _ = _req(
        "POST",
        "/api/chat?stream=false",
        token=API_SECRET,
        body={
            "user_message": "小測A的專案代號 LightSoul-Staging-Verify 是什麼？我是另一個人。",
            "conversation_id": CONV_B,
            "user_id": USER_B,
        },
        timeout=120,
    )
    am_b = ((data or {}).get("assistant_message") or "") if isinstance(data, dict) else ""
    # soft check: response should not claim personal memory of A from B's id ideally
    results.append(
        ok(
            "isolation_user_b_chat_ok",
            code == 200 and bool(am_b),
            f"code={code} snippet={am_b[:120]}",
        )
    )

    # Night Growth dry_run
    code, data, _ = _req(
        "POST",
        "/internal/night-growth/run",
        token=NG_TOKEN,
        body={"user_id": USER_A, "conversation_id": CONV_A, "dry_run": True, "force": False},
        timeout=180,
    )
    st = (data or {}).get("status") if isinstance(data, dict) else None
    results.append(
        ok(
            "night_growth_dry_run",
            code == 200 and st in ("completed_dry_run", "completed", "skipped_duplicate"),
            f"code={code} status={st} execution_id={(data or {}).get('execution_id') if isinstance(data, dict) else None}",
        )
    )

    # Night Growth formal (once)
    code, data, _ = _req(
        "POST",
        "/internal/night-growth/run",
        token=NG_TOKEN,
        body={"user_id": USER_A, "conversation_id": CONV_A, "dry_run": False, "force": False},
        timeout=180,
    )
    st = (data or {}).get("status") if isinstance(data, dict) else None
    eid = (data or {}).get("execution_id") if isinstance(data, dict) else None
    results.append(
        ok(
            "night_growth_formal",
            code == 200 and st in ("completed", "skipped_duplicate"),
            f"code={code} status={st} execution_id={eid}",
        )
    )

    # duplicate same day
    code2, data2, _ = _req(
        "POST",
        "/internal/night-growth/run",
        token=NG_TOKEN,
        body={"user_id": USER_A, "conversation_id": CONV_A, "dry_run": False, "force": False},
        timeout=180,
    )
    st2 = (data2 or {}).get("status") if isinstance(data2, dict) else None
    results.append(
        ok(
            "night_growth_idempotent_same_day",
            code2 == 200 and st2 == "skipped_duplicate",
            f"code={code2} status={st2}",
        )
    )

    # unauth night growth
    code, _, _ = _req(
        "POST",
        "/internal/night-growth/run",
        body={"user_id": USER_A, "dry_run": True},
    )
    results.append(ok("night_growth_rejects_anonymous", code == 401, f"code={code}"))

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    passed = sum(1 for r in results if r["pass"])
    failed = sum(1 for r in results if not r["pass"])
    report["summary"] = {"passed": passed, "failed": failed, "total": len(results)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
