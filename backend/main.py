# main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
except Exception as e:
    logger.warning(f"⚠️ 無法載入部分 router: {e}")

# ✅ FastAPI 生命週期事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 小晨光 AI 系統啟動中...")
    yield
    logger.info("👋 小晨光 AI 系統關閉中...")

app = FastAPI(lifespan=lifespan)

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
