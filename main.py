from dotenv import load_dotenv 
load_dotenv() 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# 引入 backend 資料夾下的各個 router
from backend.chat_router import router as chat_router
from backend.memory_router import router as memory_router
from backend.openai_handler import router as openai_router
from backend.file_upload import router as file_upload_router
from backend.healthcheck_router import router as health_router

app = FastAPI()

app.include_router(health_router, prefix="/api")

# 設定跨來源資源共享（CORS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 測試時允許所有來源，正式上線時應限制特定網域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊各個 API 路由
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

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

