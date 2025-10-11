from fastapi import APIRouter
import logging
from supabase import create_client, Client  # 要確保你 requirements.txt 有安裝 `supabase`

# 初始化 router
router = APIRouter()

# Supabase 設定（替換成你的環境變數或硬編碼）
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-or-service-role-key"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ping 用的 endpoint
@router.get("/supabase/ping")
async def supabase_ping():
    try:
        # 這裡可以改成你實際想測試的 supabase 功能，例如 list tables
        result = supabase.table("your_table_name").select("*").limit(1).execute()
        return {"message": "Supabase 連線成功", "sample": result.data}
    except Exception as e:
        logging.exception("Supabase ping error")
        return {"error": str(e)}
