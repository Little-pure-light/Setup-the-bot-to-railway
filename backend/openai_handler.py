import os
from openai import OpenAI
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
