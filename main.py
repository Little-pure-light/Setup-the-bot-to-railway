# main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import datetime
import logging
import os

# ✅ 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("main")

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

        sb_url, sb_key = _resolve_supabase_credentials()
        if not sb_url or not sb_key:
            logger.warning("⚠️ Supabase 未完整設定（SUPABASE_URL / ANON_KEY|KEY）— Auth 與記憶同步會失敗")
        else:
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
    yield
    logger.info("👋 小晨光 AI 系統關閉中...")

app = FastAPI(lifespan=lifespan)

# ✅ 選擇性 API Secret 保護中介軟體
# 若 Railway 設定了 API_SECRET 環境變數，所有 /api/* 請求需帶 Authorization: Bearer <token>
# 同時接受有效的 Supabase Auth JWT（使用者登入後跨裝置同步）
API_SECRET = os.getenv("API_SECRET", "")
AUTH_EXEMPT_PATHS = {"/api/health", "/api/auth/me", "/api/auth/sync"}


@app.middleware("http")
async def api_auth_middleware(request: Request, call_next):
    if API_SECRET and request.url.path.startswith("/api/"):
        if request.url.path not in AUTH_EXEMPT_PATHS:
            auth_header = request.headers.get("Authorization", "")
            token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
            allowed = False
            if token and token == API_SECRET:
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
                logger.warning(
                    f"⛔ 未授權存取：{request.url.path}，來源："
                    f"{request.client.host if request.client else 'unknown'}"
                )
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)

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
async def health():
    return {
        "status": "healthy",
        "service": "小晨光 AI",
        "version": "1.0.1",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

@app.get("/api/health")
async def api_health():
    return {
        "status": "healthy",
        "service": "小晨光 AI API",
        "version": "1.0.1",
        "endpoints": {
            "chat": "/api/chat",
            "memories": "/api/memories/{conversation_id}",
            "auth_me": "/api/auth/me",
            "auth_sync": "/api/auth/sync",
            "personality": "/api/personality/{user_id}",
            "usage_summary": "/api/usage/summary",
            "usage_user": "/api/usage/user/{user_id}",
            "tools": "/api/tools",
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
