from fastapi import APIRouter
from starlette.responses import JSONResponse
import os
import traceback
from supabase import create_client, Client

router = APIRouter()

@router.get("/health")
def health_check():
    result = {
        "env": "❌",
        "supabase": "❌",
        "prompt_engine": "❌",
        "chat_api": "❌",
        "error_log": [],
    }

    # 1. 檢查環境變數
    try:
        required_envs = ["SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY"]
        missing = [env for env in required_envs if not os.getenv(env)]
        if not missing:
            result["env"] = "✅"
        else:
            result["error_log"].append(f"Missing env vars: {missing}")
    except Exception as e:
        result["error_log"].append(f"ENV check error: {str(e)}")

    # 2. 測試 Supabase 連線
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        supabase: Client = create_client(url, key)
        response = supabase.table("users").select("id").limit(1).execute()
        if response.data is not None:
            result["supabase"] = "✅"
    except Exception as e:
        result["error_log"].append(f"Supabase error: {str(e)}")

    # 3. 測試 PromptEngine
    try:
        from backend.prompt_engine import PromptEngine
        _ = PromptEngine("test-conv", {})
        result["prompt_engine"] = "✅"
    except Exception as e:
        result["error_log"].append(f"PromptEngine error: {traceback.format_exc()}")

    # 4. 測試 chat API 呼叫
    try:
        import requests
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        payload = {
            "conversation_id": "health-test",
            "user_message": "你好",
            "user_name": "health-bot"
        }
        response = client.post("/api/chat", json=payload)
        if response.status_code == 200:
            result["chat_api"] = "✅"
        else:
            result["error_log"].append(f"Chat API failed: {response.text}")
    except Exception as e:
        result["error_log"].append(f"Chat API error: {traceback.format_exc()}")

    return JSONResponse(content=result)
