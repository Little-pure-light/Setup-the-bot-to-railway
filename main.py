# main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import datetime
import hmac
import logging
import os

# ✅ 設定日誌（含 secret 脫敏）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("main")
try:
    from backend.logging_utils import install_redacting_filter, new_request_id, get_request_id

    install_redacting_filter()
except Exception as _log_exc:  # pragma: no cover
    logger.warning("logging_utils 未載入: %s", _log_exc)
    def new_request_id():
        return ""
    def get_request_id():
        return ""

# ✅ 匯入各模組
try:
    from backend.chat_router import router as chat_router
    from backend.memory_router import router as memory_router
    from backend.openai_handler import router as openai_router
    from backend.file_upload import router as file_upload_router
    from backend.archive_conversation import router as archive_router
    from backend.auth_router import router as auth_router
    from backend.usage_router import router as usage_router
    from backend.tools_router import router as tools_router
    from backend.history_router import router as history_router
    from backend.voice_router import router as voice_router
    from backend.ai_kernel.debug_router import router as kernel_debug_router
    from backend.openai_compat_router import router as openai_compat_router
    from backend.internal_night_growth_router import router as internal_night_growth_router
except Exception as e:
    logger.warning(f"⚠️ 無法載入部分 router: {e}")

# ✅ FastAPI 生命週期事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 小晨光 AI 系統啟動中...")
    # 啟動時檢查 Supabase 設定（不印出 secret）
    try:
        from backend.supabase_handler import _resolve_supabase_credentials
        import socket
        from urllib.parse import urlparse

        # NOTE: _resolve_supabase_credentials() returns a 3-tuple (url, key, mode).
        # (Gate C fix: the previous 2-value unpack raised ValueError that was
        # swallowed below, so this startup check never actually ran.)
        sb_url, sb_key, sb_mode = _resolve_supabase_credentials()
        if not sb_url or not sb_key:
            logger.warning(
                "⚠️ Supabase 未完整設定（SUPABASE_URL / SERVICE_ROLE_KEY|SECRET_KEY|ANON_KEY|KEY）"
                "— Auth 與記憶同步會失敗"
            )
        else:
            # Log only the safe key-mode label, never the key itself.
            logger.info(f"🔑 Supabase key_mode={sb_mode}")
            host = urlparse(sb_url).hostname or ""
            try:
                socket.getaddrinfo(host, 443)
                logger.info(f"✅ Supabase DNS 正常 host={host}")
            except Exception as e:
                logger.error(
                    f"❌ Supabase 主機無法解析 host={host} err={e} — 請更新 .env 的 SUPABASE_URL"
                )
    except Exception as e:
        logger.warning(f"⚠️ Supabase 啟動檢查略過: {e}")
    # 啟動時檢查持久化根目錄（data/）存在且可寫，並標示掛卷狀態（只印去敏資訊）。
    # fail-open：任何失敗只記錄，不阻擋啟動（退回既有暫時磁碟行為）。
    try:
        from backend.modules.persistence import ensure_persistence_root

        _p = ensure_persistence_root()
        logger.info(
            "🗄️ persistence root=%s mode=%s writable=%s is_mount=%s",
            _p.get("root"), _p.get("mode"), _p.get("writable"), _p.get("is_mount"),
        )
        if _p.get("mode") != "volume":
            logger.warning(
                "⚠️ persistence mode=%s（非持久卷）— 重部署後 data/ 內容會遺失；"
                "請依 Runbook 於 Railway 掛載 volume 至 data/ 根。",
                _p.get("mode"),
            )
        if not _p.get("writable"):
            logger.error("❌ persistence root 不可寫 root=%s — identity/graph 寫入會失敗", _p.get("root"))
    except Exception as e:
        logger.warning(f"⚠️ persistence 啟動檢查略過: {e}")
    yield
    logger.info("👋 小晨光 AI 系統關閉中...")

app = FastAPI(lifespan=lifespan)

# ── Task008-003：統一錯誤回應 envelope（最小、附加、去敏）───────────────────────
try:
    from backend.logging_utils import ErrorCode as _EC, log_external_failure as _log_ext
except Exception:  # pragma: no cover
    class _EC:
        AUTH_ERROR = "AUTH_ERROR"
        UNKNOWN = "UNKNOWN"

    def _log_ext(_logger, _exc, code="UNKNOWN", event="error"):
        return code

_STATUS_ERROR_CODE = {
    400: "BAD_REQUEST", 401: "AUTH_ERROR", 403: "FORBIDDEN", 404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 422: "VALIDATION_ERROR",
    429: "RATE_LIMITED", 500: "INTERNAL_ERROR", 502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}
_STATUS_SAFE_MESSAGE = {
    400: "請求格式或參數有誤",
    401: "需要有效的登入或授權",
    403: "沒有權限執行此操作",
    404: "找不到資源或無權存取",
    405: "不支援的請求方法",
    409: "資源狀態衝突",
    422: "請求參數驗證失敗",
    429: "請求過於頻繁，請稍後再試",
    500: "伺服器發生未預期錯誤",
    502: "上游服務暫時無法使用",
    503: "服務暫時無法使用",
}


def _error_code_for(status_code: int) -> str:
    return _STATUS_ERROR_CODE.get(status_code, f"HTTP_{status_code}")


def _safe_message_for(status_code: int) -> str:
    return _STATUS_SAFE_MESSAGE.get(status_code, "請求無法完成")


def _error_envelope(status_code, *, error_code=None, message=None, detail=None, trace_id=None):
    """統一錯誤 envelope：success/error_code/message/trace_id；保留 detail 與 request_id 向後相容。"""
    rid = trace_id or get_request_id() or new_request_id()
    body = {
        "success": False,
        "error_code": error_code or _error_code_for(status_code),
        "message": message or _safe_message_for(status_code),
        "trace_id": rid,
        "request_id": rid,
    }
    if detail is not None:
        body["detail"] = detail
    return body, rid


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    # 去敏：一律使用中央安全訊息，絕不回傳原 exc.detail（可能含內部路徑/秘密/使用者輸入）。
    safe_msg = _safe_message_for(exc.status_code)
    # 5xx 省略 detail；4xx 保留 detail 但僅放中央安全訊息（向後相容，不含原始例外）。
    detail = None if exc.status_code >= 500 else safe_msg
    body, rid = _error_envelope(exc.status_code, message=safe_msg, detail=detail)
    headers = dict(getattr(exc, "headers", None) or {})
    headers["X-Request-ID"] = rid
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    # 去敏：只保留 loc/type/msg，不回傳使用者輸入值(input)
    safe_errors = None
    try:
        safe_errors = [
            {"loc": e.get("loc"), "type": e.get("type"), "msg": e.get("msg")}
            for e in exc.errors()
        ]
    except Exception:
        safe_errors = None
    body, rid = _error_envelope(422, detail=safe_errors)
    return JSONResponse(status_code=422, content=body, headers={"X-Request-ID": rid})


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    rid = get_request_id() or new_request_id()
    # 去敏：永遠只記 error_code / 例外型別 / request_id / event；
    # 絕不把 exception object 或 str(exc) 交給可能 verbose 的 logger（避免私人文字/內部路徑洩漏）。
    try:
        logger.error(
            "unhandled_exception error_code=%s type=%s request_id=%s event=%s",
            getattr(_EC, "UNKNOWN", "UNKNOWN"),
            type(exc).__name__,
            rid,
            "unhandled_exception",
        )
    except Exception:
        pass
    body, _rid = _error_envelope(500, trace_id=rid)
    return JSONResponse(status_code=500, content=body, headers={"X-Request-ID": rid})

# ✅ 選擇性 API Secret 保護中介軟體
# 若 Railway 設定了 API_SECRET 環境變數，/api/* 與 /v1/* 需帶 Authorization: Bearer <token>
# 同時接受有效的 Supabase Auth JWT（使用者登入後跨裝置同步）
API_SECRET = os.getenv("API_SECRET", "")
AUTH_EXEMPT_PATHS = {
    "/api/health",
    "/api/live",
    "/api/ready",
    "/api/auth/me",
    "/api/auth/sync",
    "/live",
    "/ready",
    "/health",
}


def _path_requires_api_auth(path: str) -> bool:
    """Protect legacy /api/* and OpenAI-compat /v1/* (Open WebUI)."""
    if path in AUTH_EXEMPT_PATHS:
        return False
    # /internal/* uses its own token check (NIGHT_GROWTH_INTERNAL_TOKEN)
    if path.startswith("/internal/"):
        return False
    return path.startswith("/api/") or path.startswith("/v1/")


# 注意：Starlette 後註冊的 middleware 在請求路徑上較外層先執行。
# 因此 request_id 必須「後」於 auth 註冊，才能包住 401 並寫入 X-Request-ID。
@app.middleware("http")
async def api_auth_middleware(request: Request, call_next):
    if API_SECRET and _path_requires_api_auth(request.url.path):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
        allowed = False
        # 常數時間比對，避免以回應時間差旁路推測 API_SECRET（值本身不記錄、不回顯）。
        if token and hmac.compare_digest(token.encode("utf-8"), API_SECRET.encode("utf-8")):
            allowed = True
        elif token:
            # 允許已登入的 Supabase 使用者 JWT
            try:
                from backend.supabase_handler import get_user_from_token
                if get_user_from_token(token):
                    allowed = True
            except Exception:
                allowed = False
        if not allowed:
            # 外層 request_id middleware 已設定 context；此處雙保險
            rid = get_request_id() or new_request_id()
            logger.warning(
                "⛔ 未授權存取 path=%s request_id=%s client=%s",
                request.url.path,
                rid,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error_code": "AUTH_ERROR",
                    "message": "需要有效的登入或授權",
                    "trace_id": rid,
                    "request_id": rid,
                    "detail": "Unauthorized",
                },
                headers={"X-Request-ID": rid},
            )
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """
    最外層：為每個請求附加 Request ID。
    必須包住 auth，確保 401 也有 X-Request-ID。
    """
    rid = (request.headers.get("X-Request-ID") or "").strip() or new_request_id()
    try:
        from backend.logging_utils import request_id_var

        request_id_var.set(rid)
    except Exception:
        pass
    response = await call_next(request)
    # 無論成功或 401，一律附上 header
    response.headers["X-Request-ID"] = rid
    return response

# ✅ CORS 設定（支援 Cloudflare Pages 與 Replit）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ai.dreamground.net",
        "https://ai2.dreamground.net",
        "https://*.pages.dev",
        "https://*.cloudflare.pages.dev",
        "https://*.replit.dev",
        "https://*.replit.app",
        "http://localhost:3000",
        "http://localhost:5000",
        "http://localhost:8080"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ✅ 掛載 Routers
try:
    app.include_router(chat_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(openai_router, prefix="/api")
    app.include_router(file_upload_router, prefix="/api")
    app.include_router(archive_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(usage_router, prefix="/api")
    app.include_router(tools_router, prefix="/api")
    app.include_router(history_router, prefix="/api")
    app.include_router(voice_router, prefix="/api")
    try:
        app.include_router(kernel_debug_router, prefix="/api")
    except NameError:
        pass
    # OpenAI-compatible adapter for Open WebUI (no /api prefix)
    try:
        app.include_router(openai_compat_router)
    except NameError:
        logger.warning("openai_compat_router 未載入")
    # Internal Night Growth (token-protected; no /api prefix)
    try:
        app.include_router(internal_night_growth_router)
    except NameError:
        logger.warning("internal_night_growth_router 未載入")
    logger.info("✅ 所有 router 掛載完成")
except Exception as e:
    logger.error(f"❌ 掛載 router 失敗: {e}")

# ✅ 健康檢查
@app.get("/")
async def root():
    return {
        "message": "小晨光 AI 靈魂系統 Bot",
        "version": "1.0.1",
        "status": "running",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

@app.get("/health")
@app.get("/live")
@app.get("/api/live")
async def liveness():
    """Liveness：程序存活（不依賴外部服務）。"""
    from backend.health import liveness_payload

    return liveness_payload()


@app.get("/ready")
@app.get("/api/ready")
async def readiness():
    """
    Readiness：環境變數 / 可選 DNS（非 DB 探測，不消耗 OpenAI Token）。
    DNS 若啟用則於 asyncio.to_thread 執行。
    """
    from backend.health import readiness_payload_async

    body = await readiness_payload_async()
    code = 200 if body.get("status") in ("ok", "degraded") else 503
    return JSONResponse(status_code=code, content=body)


@app.get("/api/health")
async def api_health():
    from backend.health import APP_VERSION, liveness_payload

    live = liveness_payload()
    return {
        "status": "healthy" if live.get("status") == "ok" else live.get("status"),
        "service": "小晨光 AI API",
        "version": APP_VERSION,
        "endpoints": {
            "chat": "/api/chat",
            "memories": "/api/memories/{conversation_id}",
            "auth_me": "/api/auth/me",
            "auth_sync": "/api/auth/sync",
            "personality": "/api/personality/{user_id}",
            "usage_summary": "/api/usage/summary",
            "usage_user": "/api/usage/user/{user_id}",
            "tools": "/api/tools",
            "upload_file": "/api/upload_file",
            "vision_analyze": "/api/vision/analyze",
            "history_conversations": "/api/history/conversations",
            "history_search": "/api/history/search",
            "history_summarize": "/api/history/summarize",
            "voice_status": "/api/voice/status",
            "voice_settings": "/api/voice/settings/{user_id}",
            "voice_prepare_speech": "/api/voice/prepare-speech",
            "voice_events": "/api/voice/events",
            "live": "/api/live",
            "ready": "/api/ready",
            "health": "/api/health"
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

# ✅ 若 /api/chat 沒被 router 提供，補上一個後備 POST 路由
@app.post("/api/chat")
async def fallback_chat(req: Request):
    try:
        body = await req.json()
        user_message = body.get("user_message", "")
        logger.info(f"💬 收到前端訊息: {user_message}")
        return {
            "reply": f"這是後端測試回覆：你說了「{user_message}」",
            "status": "ok"
        }
    except Exception as e:
        logger.error(f"⚠️ Chat Endpoint 錯誤: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
