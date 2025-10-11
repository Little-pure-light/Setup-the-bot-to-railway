import os
from supabase import create_client, Client
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

router = APIRouter()
_supabase_client = None

def get_supabase_client() -> Client:
    """獲取 Supabase 客戶端實例"""
    global _supabase_client
    
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("缺少 SUPABASE_URL 或 SUPABASE_KEY 環境變數")
        
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    return _supabase_client

# ✅ 新增測試用 API 路由
@router.get("/supabase/ping")
async def supabase_ping():
    try:
        client = get_supabase_client()
        return {"message": "✅ Supabase 初始化成功", "url": SUPABASE_URL}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
