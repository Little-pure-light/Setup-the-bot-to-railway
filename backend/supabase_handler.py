from fastapi import APIRouter
from backend.utils.supabase_client import supabase
import logging

router = APIRouter()

@router.get("/supabase/ping")
async def supabase_ping():
    try:
        logging.info("🔍 正在呼叫 Supabase 的 profiles 資料表")
        response = supabase.table("profiles").select("*").limit(1).execute()
        logging.info(f"✅ Supabase 回應：{response}")
        return {"status": "success", "data": response}
    except Exception as e:
        logging.error(f"❌ Supabase 錯誤：{e}")
        return {"status": "error", "message": str(e)}

