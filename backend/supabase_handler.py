# ✅ 完整補強過的 supabase_handler.py（包含錯誤處理與 debug log）

from fastapi import APIRouter
from supabase import create_client, Client
import os
import traceback

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_supabase_client = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        print("[DEBUG] Initializing Supabase client...")
        print("[DEBUG] SUPABASE_URL:", SUPABASE_URL)
        print("[DEBUG] SUPABASE_KEY present:", bool(SUPABASE_KEY))

        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("[ERROR] 環境變數 SUPABASE_URL 或 SUPABASE_KEY 缺失")
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("[DEBUG] Supabase client initialized successfully.")
        except Exception as e:
            print("[ERROR] 建立 Supabase 客戶端失敗：", str(e))
            traceback.print_exc()
            raise
    return _supabase_client


@router.get("/api/supabase/ping")
def ping_supabase():
    try:
        client = get_supabase_client()
        response = client.table("users").select("*").limit(1).execute()
        print("[DEBUG] Supabase ping response:", response)
        return {"status": "success", "sample": response.data}
    except Exception as e:
        print("[ERROR] /api/supabase/ping 失敗：", str(e))
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
