import os
import json
from openai import OpenAI, AsyncOpenAI
from typing import AsyncGenerator, Optional, List, Dict, Any, Union
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request

from backend.token_tracker import usage_from_openai

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


def _build_async_openai_client() -> AsyncOpenAI:
    """建立 AsyncOpenAI 客戶端（支援 org）"""
    kwargs = {"api_key": OPENAI_API_KEY}
    if OPENAI_ORG_ID:
        kwargs["organization"] = OPENAI_ORG_ID
    return AsyncOpenAI(**kwargs)


async def generate_response(
    client: OpenAI,
    messages: list,
    model: str = "gpt-4o-mini",
    max_tokens: int = 1000,
    temperature: float = 0.8,
    return_usage: bool = False,
) -> Union[str, Dict[str, Any]]:
    """
    非串流聊天。
    return_usage=True 時回傳 {"content": str, "usage": {...}, "model": str}
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        reply = response.choices[0].message.content if response.choices else ""
        usage = usage_from_openai(getattr(response, "usage", None))
        print(f"💬 AI 回應: {reply[:60]}{'...' if len(reply) > 60 else ''}")
        print(f"📊 tokens in={usage['prompt_tokens']} out={usage['completion_tokens']}")
        if return_usage:
            return {"content": reply, "usage": usage, "model": model}
        return reply
    except Exception as e:
        print(f"❌ OpenAI API 錯誤: {e}")
        raise


async def generate_response_stream(
    messages: list,
    model: str = "gpt-4o-mini",
    temperature: float = 0.8,
    max_tokens: int = 2000,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    OpenAI Streaming 回應產生器。
    yield:
      {"type": "content", "text": "..."}
      {"type": "usage", "usage": {...}, "model": model}
    """
    if not OPENAI_API_KEY:
        yield {"type": "content", "text": "[ERROR] 缺少 OPENAI_API_KEY"}
        return

    client = _build_async_openai_client()
    usage_data = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        create_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # 串流結尾回傳 usage（新版 API）
        try:
            create_kwargs["stream_options"] = {"include_usage": True}
            stream = await client.chat.completions.create(**create_kwargs)
        except Exception:
            create_kwargs.pop("stream_options", None)
            stream = await client.chat.completions.create(**create_kwargs)

        async for chunk in stream:
            if getattr(chunk, "usage", None):
                usage_data = usage_from_openai(chunk.usage)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield {"type": "content", "text": content}

        yield {"type": "usage", "usage": usage_data, "model": model}
    except Exception as e:
        print(f"❌ OpenAI Streaming 錯誤: {e}")
        yield {"type": "content", "text": f"[ERROR] {str(e)}"}
        yield {"type": "usage", "usage": usage_data, "model": model}


async def generate_response_with_tools(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.8,
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """
    支援 Tool Calling 的 OpenAI 呼叫。
    若發生任何錯誤，回傳 finish_reason="error" 讓上層降級處理。
    """
    if not OPENAI_API_KEY:
        return {
            "content": "",
            "tool_calls": [],
            "finish_reason": "error",
            "raw_message": None,
            "error": "missing_api_key",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "model": model,
        }

    client = _build_async_openai_client()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        usage = usage_from_openai(getattr(response, "usage", None))
        return {
            "content": choice.message.content or "",
            "tool_calls": choice.message.tool_calls or [],
            "finish_reason": choice.finish_reason,
            "raw_message": choice.message,
            "usage": usage,
            "model": model,
        }
    except Exception as e:
        err_msg = str(e)
        if "context_length_exceeded" in err_msg or "maximum context" in err_msg.lower():
            print(f"⚠️ Token 超過限制，嘗試不帶工具重新呼叫")
            return {
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "raw_message": None,
                "error": "context_length_exceeded",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "model": model,
            }
        print(f"❌ generate_response_with_tools 錯誤: {e}")
        return {
            "content": "",
            "tool_calls": [],
            "finish_reason": "error",
            "raw_message": None,
            "error": err_msg,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "model": model,
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
        result = await generate_response(
            client, messages, model, max_tokens, temperature, return_usage=True
        )
        return {"response": result["content"], "usage": result["usage"], "model": model}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
