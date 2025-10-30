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

@router.get("/health/modules")
async def modules_health_check():
    """
    模組健康檢查
    
    返回:
        所有模組的健康狀態
    """
    try:
        from backend.core_controller import get_core_controller
        
        controller = await get_core_controller()
        health_status = await controller.health_check_all()
        
        return JSONResponse(content={
            "status": "success",
            "data": health_status
        })
        
    except Exception as e:
        return JSONResponse(content={
            "status": "error",
            "error": str(e),
            "fallback": {
                "controller": "not_initialized",
                "message": "模組系統尚未初始化或發生錯誤"
            }
        })

@router.get("/health/detailed")
async def detailed_health_check():
    """
    詳細健康檢查（包含環境變數與模組狀態）
    
    返回:
        完整系統狀態
    """
    env_status = {
        "OPENAI_API_KEY": "✅" if os.getenv("OPENAI_API_KEY") else "❌",
        "SUPABASE_URL": "✅" if os.getenv("SUPABASE_URL") else "❌",
        "SUPABASE_ANON_KEY": "✅" if os.getenv("SUPABASE_ANON_KEY") else "❌",
        "REDIS_URL": "✅" if os.getenv("REDIS_URL") else "⚠️ (using mock)"
    }
    
    try:
        from backend.core_controller import get_core_controller
        controller = await get_core_controller()
        modules_health = await controller.health_check_all()
    except Exception as e:
        modules_health = {"error": str(e)}
    
    return JSONResponse(content={
        "status": "healthy",
        "system": {
            "name": "XiaoChenGuang AI",
            "version": "2.0.0",
            "phase": "Phase 2 - Modular Architecture"
        },
        "environment": env_status,
        "modules": modules_health
    })
