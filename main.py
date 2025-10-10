from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chat_router import router as chat_router
from memory_router import router as memory_router
from file_upload import router as file_router

app = FastAPI(title="小宸光 AI 靈魂系統 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(memory_router, prefix="/api", tags=["Memory"])
app.include_router(file_router, prefix="/api", tags=["File"])

@app.get("/")
async def root():
    return {
        "message": "小宸光 AI 靈魂系統 API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    # 支援 Railway 的 $PORT 環境變數
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
