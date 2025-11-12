"""
Copilot Memory Brain - Main Application
FastAPI 主程式（Port 8001）
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os
from datetime import datetime

# 添加專案根目錄到路徑
project_root = os.path.join(os.path.dirname(__file__), '../..')
sys.path.insert(0, project_root)

from config import config

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("copilot_memory_brain")

# 生命週期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🧠 Copilot 記憶腦啟動中...")
    
    # 驗證配置
    if not config.validate():
        logger.error("❌ 配置驗證失敗，請檢查環境變數")
    else:
        logger.info("✅ 配置驗證通過")
    
    yield
    
    logger.info("👋 Copilot 記憶腦關閉中...")

# 創建 FastAPI 應用
app = FastAPI(
    title="Copilot Memory Brain",
    description="VS Code Copilot 外掛記憶系統",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 配置（與主系統相同）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ai.dreamground.net",
        "https://ai2.dreamground.net",
        "https://*.pages.dev",
        "https://*.cloudflare.pages.dev",
        "https://*.railway.app",
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

# 匯入路由
try:
    from routers import copilot_router
    from routers import memory_router
    from routers import reflection_router
    
    app.include_router(copilot_router.router, prefix=config.API_PREFIX, tags=["Copilot"])
    app.include_router(memory_router.router, prefix=config.API_PREFIX, tags=["Memory"])
    app.include_router(reflection_router.router, prefix=config.API_PREFIX, tags=["Reflection"])
    
    logger.info("✅ 所有路由已掛載")
except Exception as e:
    logger.error(f"❌ 路由掛載失敗: {e}")

# 根路由
@app.get("/")
async def root():
    return {
        "service": "Copilot Memory Brain",
        "version": "2.0.0",
        "status": "running",
        "description": "VS Code Copilot 外掛記憶系統",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "copilot": f"{config.API_PREFIX}/ask_copilot",
            "memory": f"{config.API_PREFIX}/memory/recent",
            "reflection": f"{config.API_PREFIX}/reflection/latest",
            "health": "/health"
        }
    }

# 健康檢查
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Copilot Memory Brain",
        "version": "2.0.0",
        "port": config.PORT,
        "timestamp": datetime.utcnow().isoformat()
    }

# 啟動訊息
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🚀 啟動 Copilot Memory Brain on port {config.PORT}")
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        log_level="info"
    )
