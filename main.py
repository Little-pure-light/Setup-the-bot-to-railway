from dotenv import load_dotenv 
load_dotenv() 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import os

# 引入 backend 資料夾下的各個 router
from backend.chat_router import router as chat_router
from backend.memory_router import router as memory_router
from backend.openai_handler import router as openai_router
from backend.file_upload import router as file_upload_router
from backend.healthcheck_router import router as health_router

# 全域變數儲存後台任務
background_tasks = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時執行
    print("\n" + "="*60)
    print("🚀 XiaoChenGuang AI System 啟動中...")
    print("="*60)
    
    # 啟動記憶刷寫工作器
    flush_enabled = os.getenv("ENABLE_MEMORY_FLUSH", "true").lower() == "true"
    
    if flush_enabled:
        try:
            from backend.modules.memory.core import MemoryCore
            from backend.jobs.memory_flush_worker import create_flush_worker
            
            memory_core = MemoryCore()
            flush_interval = int(os.getenv("MEMORY_FLUSH_INTERVAL", "300"))
            worker = create_flush_worker(memory_core, interval_seconds=flush_interval)
            
            # 在背景啟動工作器
            flush_task = asyncio.create_task(worker.start())
            background_tasks['memory_flush'] = {
                'task': flush_task,
                'worker': worker
            }
            
            print(f"✅ 記憶刷寫工作器已啟動（間隔: {flush_interval}秒）")
        except Exception as e:
            print(f"⚠️ 記憶刷寫工作器啟動失敗: {e}")
    else:
        print("ℹ️ 記憶刷寫工作器已停用")
    
    print("="*60)
    print("✅ 系統啟動完成")
    print("="*60 + "\n")
    
    yield
    
    # 關閉時執行
    print("\n" + "="*60)
    print("👋 XiaoChenGuang AI System 關閉中...")
    print("="*60)
    
    # 停止記憶刷寫工作器
    if 'memory_flush' in background_tasks:
        worker_info = background_tasks['memory_flush']
        worker_info['worker'].stop()
        
        try:
            await asyncio.wait_for(worker_info['task'], timeout=5.0)
            print("✅ 記憶刷寫工作器已停止")
        except asyncio.TimeoutError:
            print("⚠️ 記憶刷寫工作器停止超時，強制終止")
            worker_info['task'].cancel()
    
    print("="*60)
    print("✅ 系統已安全關閉")
    print("="*60 + "\n")

app = FastAPI(lifespan=lifespan)

# ✅ 設定跨來源資源共享（CORS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ai.dreamground.net",   # Cloudflare Pages 前端網址
        "https://ai2.dreamground.net",  # 後端自己的網址
        "https://*.pages.dev"           # Cloudflare 預設部署子網域（保險用）
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊各個 API 路由
app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(openai_router, prefix="/api")
app.include_router(file_upload_router, prefix="/api")

# 根路由檢查是否運行中
@app.get("/")
async def root():
    return {
        "message": "小晨光 AI 靈魂系統 Bot",
        "version": "1.0.0",
        "status": "running"
    }

from fastapi.responses import JSONResponse
import datetime

# 新增測試日期的API
@app.get("/api/test-date")
async def test_date():
    now = datetime.datetime.utcnow()  # 獲取標準的 UTC 時間
    iso_date = now.isoformat() + "Z"  # 格式化為 ISO 標準
    return JSONResponse(content={"timestamp": iso_date})

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
