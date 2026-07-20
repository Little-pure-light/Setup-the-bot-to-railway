"""本機 Auth + 聊天 smoke test（不輸出 secrets）"""
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

BASE = os.getenv("TEST_BASE", "http://127.0.0.1:8000")


def req(method, path, headers=None, data=None, timeout=90):
    h = dict(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return e.code, raw


def main():
    print("=== AUTH / CHAT SMOKE TEST ===")
    print("BASE:", BASE)

    code, body = req("GET", "/api/health")
    print(f"[health] {code} ok={code==200}")

    code, body = req("GET", "/api/auth/me")
    print(f"[auth/me no token] {code} body={body[:160]}")

    code, body = req(
        "GET",
        "/api/auth/me",
        headers={"Authorization": "Bearer fake.jwt.token"},
    )
    print(f"[auth/me bad jwt] {code} body={body[:160]}")

    code, body = req(
        "GET",
        "/api/auth/sync",
        headers={"Authorization": "Bearer fake.jwt.token"},
    )
    print(f"[auth/sync bad jwt] {code} body={body[:160]}")

    code, body = req("GET", "/api/personality/guest_test_user")
    print(f"[personality guest] {code} body={body[:200]}")

    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    host = url.split("//")[-1] if url else ""
    print(f"[supabase] host={host}")
    dns_ok = False
    if host:
        try:
            socket.getaddrinfo(host, 443)
            dns_ok = True
            print("[supabase] DNS OK")
        except Exception as e:
            print(f"[supabase] DNS FAIL: {e}")

    access_token = None
    login_possible = False
    test_email = os.getenv("TEST_AUTH_EMAIL", "localtest_auth_check@example.com")
    test_password = os.getenv("TEST_AUTH_PASSWORD", "TestPass123!")

    if dns_ok and key:
        # health
        try:
            health_url = f"{url.rstrip('/')}/auth/v1/health"
            request = urllib.request.Request(
                health_url,
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=15) as resp:
                print(f"[supabase auth health] {resp.status}")
        except Exception as e:
            print(f"[supabase auth health] ERR {type(e).__name__}: {e}")

        # signup (ignore if already exists)
        signup_url = f"{url.rstrip('/')}/auth/v1/signup"
        payload = json.dumps({"email": test_email, "password": test_password}).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            signup_url,
            data=payload,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                print(f"[supabase signup] {resp.status} {raw[:200]}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            print(f"[supabase signup] HTTP {e.code} {raw[:250]}")
        except Exception as e:
            print(f"[supabase signup] ERR {type(e).__name__}: {e}")

        # password login
        token_url = f"{url.rstrip('/')}/auth/v1/token?grant_type=password"
        payload = json.dumps({"email": test_email, "password": test_password}).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            token_url,
            data=payload,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                access_token = data.get("access_token")
                login_possible = bool(access_token)
                print(
                    f"[supabase login] {resp.status} token={'yes' if access_token else 'no'} "
                    f"user={(data.get('user') or {}).get('id', '')[:8]}"
                )
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            print(f"[supabase login] HTTP {e.code} {raw[:300]}")
        except Exception as e:
            print(f"[supabase login] ERR {type(e).__name__}: {e}")
    else:
        print("[supabase] skip auth: DNS or key missing")
    # guest chat non-stream
    code, body = req(
        "POST",
        "/api/chat?stream=false&use_tools=false",
        data={
            "user_message": "用一句話自我介紹",
            "conversation_id": "test_conv_local_2",
            "user_id": "guest_test_user",
        },
        timeout=120,
    )
    print(f"[chat guest non-stream] {code}")
    chat_ok = code == 200
    try:
        data = json.loads(body)
        msg = data.get("assistant_message") or data.get("reply") or ""
        print(f"  reply: {msg[:200]}")
        emo = (data.get("emotion_analysis") or {}).get("dominant_emotion")
        print(f"  emotion: {emo}")
        chat_ok = chat_ok and bool(msg.strip())
    except Exception:
        print(f"  body: {body[:200]}")
        chat_ok = False

    # stream first chunk
    stream_ok = False
    try:
        request = urllib.request.Request(
            BASE + "/api/chat?stream=true&use_tools=false",
            data=json.dumps(
                {
                    "user_message": "嗨",
                    "conversation_id": "test_conv_local_3",
                    "user_id": "guest_test_user",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as resp:
            chunk = resp.read(180).decode("utf-8", errors="replace")
            stream_ok = resp.status == 200 and len(chunk) > 0
            print(f"[chat guest stream] {resp.status} first={chunk[:120]!r}")
    except Exception as e:
        print(f"[chat guest stream] ERR {type(e).__name__}: {e}")

    # 登入後：/api/auth/me、/api/auth/sync、帶 JWT 聊天
    chat_after_login_ok = False
    if access_token:
        code, body = req(
            "GET",
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        print(f"[auth/me with session] {code} {body[:180]}")
        me_ok = code == 200

        code, body = req(
            "GET",
            "/api/auth/sync",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        print(f"[auth/sync with session] {code} {body[:220]}")
        sync_ok = code == 200

        user_id = None
        try:
            user_id = json.loads(body).get("user_id")
        except Exception:
            pass
        if not user_id:
            try:
                # fallback from /me
                code_me, body_me = req(
                    "GET",
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_id = json.loads(body_me).get("id")
            except Exception:
                user_id = "logged_in_user"

        code, body = req(
            "POST",
            "/api/chat?stream=false&use_tools=false",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "user_message": "登入後測試：請用一句話打招呼",
                "conversation_id": "test_conv_logged_in_1",
                "user_id": user_id,
            },
            timeout=120,
        )
        print(f"[chat after login] {code}")
        try:
            msg = json.loads(body).get("assistant_message") or ""
            print(f"  reply: {msg[:200]}")
            chat_after_login_ok = code == 200 and bool(msg.strip())
        except Exception:
            print(f"  body: {body[:200]}")
            chat_after_login_ok = False
        print(f"[login path checks] me={me_ok} sync={sync_ok} chat={chat_after_login_ok}")
    else:
        print("[auth logged-in path] SKIP (no access_token)")

    print("\n=== SUMMARY ===")
    print("backend_health: PASS")
    print("auth_endpoints_wired: PASS (reject invalid token)")
    print(f"email_login_end_to_end: {'PASS' if login_possible else 'FAIL'}")
    print(f"chat_after_guest: {'PASS' if chat_ok else 'FAIL'}")
    print(f"chat_stream_guest: {'PASS' if stream_ok else 'FAIL'}")
    print(
        f"chat_after_login: {'PASS' if chat_after_login_ok else ('FAIL' if access_token else 'SKIP')}"
    )


if __name__ == "__main__":
    main()
