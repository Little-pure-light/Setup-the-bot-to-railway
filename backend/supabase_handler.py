from fastapi import APIRouter
from supabase import create_client
import os
from dotenv import load_dotenv

# 讀取本地或 Railway 的環境變數
load_dotenv()

# 🚀 這裡名稱要對應 Railway 的變數名稱
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")  # ✅ 關鍵修改點

# 建立 Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 初始化 FastAPI Router（供 main.py 使用）
router = APIRouter()
