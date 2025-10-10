import os
from openai import OpenAI
from dotenv import load_dotenv

# 載入 .env 檔
load_dotenv()

# 從環境變數讀取金鑰與組織、專案 ID
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")

def get_openai_client() -> OpenAI:
    """
    建立 OpenAI Client 實例。
    自動偵測新版 () 或舊版 (sk-) APIsk-proj- Key。
    """
    if not OPENAI_API_KEY:
        raise ValueError("❌ 缺少 OPENAI_API_KEY 環境變數，請在 Replit Secrets 中設定")

    # Debug：顯示金鑰前幾碼（安全截斷）
    print(f"🔍 偵測到 API KEY: {OPENAI_API_KEY[:10]}...(已截斷)")

    # 建立 OpenAI 客戶端（organization 參數可選）
    if OPENAI_ORG_ID:
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            organization=OPENAI_ORG_ID
        )
    else:
        client = OpenAI(api_key=OPENAI_API_KEY)

    print("✅ OpenAI 客戶端初始化成功")
    return client


async def generate_response(
    client: OpenAI,
    messages: list,
    model: str = "gpt-4o-mini",
    max_tokens: int = 1000,
    temperature: float = 0.8
) -> str:
    """生成 AI 回應"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        # 提取回應文字
        reply = response.choices[0].message.content if response.choices and len(response.choices) > 0 else ""
        if reply:
            print(f"💬 AI 回應內容: {reply[:60]}{'...' if len(reply) > 60 else ''}")
        else:
            print("💬 無 AI 回應")
        return reply

    except Exception as e:
        print(f"❌ OpenAI API 錯誤: {e}")
        raise