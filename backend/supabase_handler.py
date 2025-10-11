from fastapi import APIRouter
import os
import logging

router = APIRouter()

@router.get("/api/supabase/ping")
async def ping_supabase():
    logging.info("🔍 [Supabase Ping] API Called")

    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url:
            logging.error("❌ 環境變數 'SUPABASE_URL' 未設置")
            return {"error": "Missing SUPABASE_URL in environment variables."}

        if not supabase_key:
            logging.error("❌ 環境變數 'SUPABASE_SERVICE_ROLE_KEY' 未設置")
            return {"error": "Missing SUPABASE_SERVICE_ROLE_KEY in environment variables."}

        logging.info(f"✅ SUPABASE_URL: {supabase_url}")
        logging.info(f"✅ SUPABASE_SERVICE_ROLE_KEY: {supabase_key[:6]}...(隱藏其餘)")

        # 模擬連接成功（你可加真連線邏輯）
        return {"message": "Supabase environment is correctly configured."}

    except Exception as e:
        logging.exception("🔥 發生例外錯誤：")
        return {"error": str(e)}
