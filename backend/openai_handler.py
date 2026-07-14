import os
import json
from openai import OpenAI, AsyncOpenAI
from typing import AsyncGenerator, Optional, List, Dict, Any
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request

# 初始化 FastAPI router
router = APIRouter()

# 載入 .env 檔
load_dotenv()

# 從環境變數讀取金鑰與組織、專案 ID
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")

def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("❌ 缺少 OPENAI_API_KEY 環境變數")

    if OPENAI_ORG_ID:
        client = OpenAI(api_key=OPENAI_API_KEY, organization=OPENAI_ORG_ID)
    else:
        client = OpenAI(api_key=OPENAI_API_KEY)

    print("✅ OpenAI 客戶端初始化成功")
    return client

async def generate_response(client: OpenAI, messages: list, model: str = "gpt-4o-mini", max_tokens: int = 1000, temperature: float = 0.8) -> str:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        reply = response.choices[0].message.content if response.choices else ""
        print(f"💬 AI 回應: {reply[:60]}{'...' if len(reply) > 60 else ''}")
        return reply
    except Exception as e:
        print(f"❌ OpenAI API 錯誤: {e}")
        raise


async def generate_response_stream(
    messages: list,
    model: str = "gpt-4o-mini",
    temperature: float = 0.8,
    max_tokens: int = 2000
) -> AsyncGenerator[str, None]:
    """
    OpenAI Streaming 回應產生器，逐字 yield 內容。
    """
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        yield f"[ERROR] {str(e)}"


async def generate_response_with_tools(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.8,
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """
    支援 Tool Calling 的 OpenAI 呼叫。
    若發生任何錯誤，回傳 finish_reason="error" 讓上層降級處理。

    回傳:
        {
            "content": str,           # 最終回答文字
            "tool_calls": list,       # AI 決定要呼叫的工具（可能為空）
            "finish_reason": str,     # "stop", "tool_calls", 或 "error"
            "raw_message": object     # 原始 message 物件（可能為 None）
        }
    """
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=max_tokens
        )
        choice = response.choices[0]
        return {
            "content": choice.message.content or "",
            "tool_calls": choice.message.tool_calls or [],
            "finish_reason": choice.finish_reason,
            "raw_message": choice.message
        }
    except Exception as e:
        err_msg = str(e)
        if "context_length_exceeded" in err_msg or "maximum context" in err_msg.lower():
            print(f"⚠️ Token 超過限制，嘗試不帶工具重新呼叫")
            # Token 超限：降級為不帶工具的普通呼叫
            return {
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "raw_message": None,
                "error": "context_length_exceeded"
            }
        print(f"❌ generate_response_with_tools 錯誤: {e}")
        return {
            "content": "",
            "tool_calls": [],
            "finish_reason": "error",
            "raw_message": None,
            "error": err_msg
        }

# ✅ 新增一個 POST API 路由：/api/openai/chat
@router.post("/openai/chat")
async def chat_with_openai(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        model = data.get("model", "gpt-4o-mini")
        max_tokens = data.get("max_tokens", 1000)
        temperature = data.get("temperature", 0.8)

        client = get_openai_client()
        reply = await generate_response(client, messages, model, max_tokens, temperature)
        return {"response": reply}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
