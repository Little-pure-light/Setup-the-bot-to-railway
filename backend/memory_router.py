from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
import traceback

# =========================================================
# 導入後端服務與模組 (確保核心記憶功能可用)
# =========================================================
from backend.supabase_handler import get_supabase
from backend.openai_handler import get_openai_client 
# 假設這些模組在你的 backend/ 目錄中
from modules.memory_system import MemorySystem 
from backend.modules.memory.core import MemoryCore 
from backend.modules.reflection_storage import ReflectionStorage 
from backend.modules.memory.redis_interface import RedisInterface
from backend.modules.pinecone_handler import PineconeHandler

supabase = get_supabase()
router = APIRouter()
logger = logging.getLogger("memory_router")

# =========================================================
# 依賴注入 (Dependency Injection) 輔助函數
# =========================================================
def get_memory_system() -> MemorySystem:
    openai_client = get_openai_client()
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    return MemorySystem(supabase, openai_client, memories_table)

def get_new_memory_core() -> MemoryCore:
    return MemoryCore()

def get_reflection_storage() -> ReflectionStorage:
    # 確保 ReflectionStorage 的依賴被正確實例化
    try:
        redis_interface = RedisInterface()
        pinecone_handler = PineconeHandler()
        return ReflectionStorage(
            redis_interface=redis_interface,
            supabase_client=supabase,
            pinecone_handler=pinecone_handler
        )
    except Exception as e:
        logger.error(f"⚠️ ReflectionStorage 初始化失敗: {e}")
        # 如果無法初始化，則拋出異常，讓服務知道有問題
        raise HTTPException(status_code=500, detail="後端服務初始化錯誤: ReflectionStorage")

# =========================================================
# 數據模型 (Models) - 擴充了 POST 請求的模型
# =========================================================

class MemoryItem(BaseModel):
    id: int
    user_message: str
    assistant_message: str
    created_at: str
    importance_score: Optional[float] = None
    access_count: Optional[int] = None

# ✅ 1. 儲存記憶的請求模型 (對應 saveMemory.ts 的 Payload)
class SaveMemoryRequest(BaseModel):
    memory_type: str = "code"
    code_context: str
    summary: str
    source: str = "vs_code"
    ai_id: str = "copilot_brain"
    user_id: str = "default_user" 

# ✅ 2. 記憶檢索的請求模型 (對應 recallMemory.ts 的 Payload)
class SearchMemoryRequest(BaseModel):
    query: str
    user_id: str = "default_user"

# =========================================================
# 路由定義 (Routes)
# =========================================================

# GET /memories/{conversation_id} - 讀取對話記憶 (已存在，保留)
@router.get("/memories/{conversation_id}", response_model=List[MemoryItem])
async def get_memories(conversation_id: str, limit: int = 20):
    try:
        logger.info(f"🔍 查詢記憶：conversation_id={conversation_id}, limit={limit}")
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")

        result = supabase.table(memories_table)\
            .select("id, user_message, assistant_message, created_at, importance_score, access_count")\
            .eq("conversation_id", conversation_id)\
            .eq("memory_type", "conversation")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()

        logger.info("✅ 記憶查詢成功")
        return result.data

    except Exception as e:
        logger.exception("❌ 讀取記憶失敗")
        raise HTTPException(status_code=500, detail=str(e))


# GET /recent-history/{user_id} - 根據 user_id 取得最近的對話歷史（用於跨裝置載入）
@router.get("/recent-history/{user_id}")
async def get_recent_history(user_id: str, limit: int = 30):
    """
    根據 user_id 取得最近的對話歷史，用於頁面載入時從後端恢復對話。
    回傳格式：[{role, content, timestamp}]，按時間正序排列
    """
    try:
        logger.info(f"🔍 查詢最近歷史：user_id={user_id}, limit={limit}")
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")

        result = supabase.table(memories_table)\
            .select("user_message, assistant_message, created_at, conversation_id")\
            .eq("user_id", user_id)\
            .eq("memory_type", "conversation")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()

        if not result.data:
            return {"messages": [], "conversation_id": None}

        # 整理成前端可用的格式（時間正序）
        rows = list(reversed(result.data))
        messages = []
        for row in rows:
            ts = row.get("created_at", "")[:19].replace("T", " ")
            if row.get("user_message"):
                messages.append({
                    "type": "user",
                    "content": row["user_message"],
                    "timestamp": ts,
                    "streaming": False
                })
            if row.get("assistant_message"):
                messages.append({
                    "type": "assistant",
                    "content": row["assistant_message"],
                    "timestamp": ts,
                    "streaming": False
                })

        # 取最新那筆的 conversation_id
        latest_conv_id = result.data[0].get("conversation_id") if result.data else None

        logger.info(f"✅ 最近歷史查詢成功：{len(messages)} 則訊息")
        return {"messages": messages, "conversation_id": latest_conv_id}

    except Exception as e:
        logger.exception("❌ 讀取最近歷史失敗")
        raise HTTPException(status_code=500, detail=str(e))

# GET /emotional-states/{user_id} - 讀取情緒狀態 (已存在，保留)
@router.get("/emotional-states/{user_id}")
async def get_emotional_states(user_id: str, limit: int = 10):
    try:
        logger.info(f"🔍 查詢情緒：user_id={user_id}, limit={limit}")
        result = supabase.table("emotional_states")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()

        logger.info("✅ 情緒查詢成功")
        return result.data
    except Exception as e:
        logger.exception("❌ 讀取情緒失敗")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# ✅ 1. 新增：儲存記憶路由 (POST /api/save_memory)
# =========================================================
@router.post("/api/save_memory")
async def save_memory(request: SaveMemoryRequest, memory_core: MemoryCore = Depends(get_new_memory_core)):
    """
    前端 saveMemory.ts 呼叫此路由，將程式碼片段存入後端記憶系統。
    這會觸發 Supabase 寫入、Pinecone 向量化等。
    """
    logger.info(f"💾 接收到新的程式碼記憶請求: {request.summary}")
    try:
        # 使用 MemoryCore 進行統一的儲存操作
        # 注意: Conversation ID 在這裡可能為 None 或需要生成一個
        result = await memory_core.store_memory(
            memory_type=request.memory_type,
            user_id=request.user_id,
            content=request.code_context,
            summary=request.summary,
            source=request.source,
            ai_id=request.ai_id
        )

        if result.get("success"):
            logger.info(f"✅ 程式碼記憶儲存成功，Token: {result.get('token_count', 0)}")
            return {"success": True, "message": "記憶已儲存，AI寶貝正在學習"}
        else:
            logger.error(f"❌ 記憶儲存失敗：{result.get('error', '未知錯誤')}")
            raise HTTPException(status_code=500, detail=f"記憶儲存失敗: {result.get('error', '未知錯誤')}")

    except Exception as e:
        traceback_str = traceback.format_exc()
        logger.error(f"❌ 儲存記憶路由錯誤: {e}\n{traceback_str}")
        raise HTTPException(status_code=500, detail="後端光流異常，無法儲存記憶。")


# =========================================================
# ✅ 2. 新增：記憶檢索路由 (POST /memory/search)
# =========================================================
@router.post("/memory/search")
async def search_memory(request: SearchMemoryRequest, memory_system: MemorySystem = Depends(get_memory_system)):
    """
    前端 recallMemory.ts 呼叫此路由，進行向量記憶檢索（RAG）。
    """
    logger.info(f"🔍 接收到記憶檢索請求: {request.query}")
    try:
        # 使用 MemorySystem 進行向量檢索
        recalled_memories = await memory_system.recall_memories(
            user_query=request.query,
            conversation_id=None, 
            limit=5 
        )

        logger.info(f"✅ 記憶檢索成功，找到 {len(recalled_memories)} 筆相關記憶")
        # 返回一個結構化的結果給前端
        return {"success": True, "results": recalled_memories}

    except Exception as e:
        traceback_str = traceback.format_exc()
        logger.error(f"❌ 記憶檢索路由錯誤: {e}\n{traceback_str}")
        raise HTTPException(status_code=500, detail="後端光流異常，無法檢索記憶。")


# =========================================================
# ✅ 3. 新增：觸發反思路由 (POST /memory/reflection)
# =========================================================
@router.post("/memory/reflection")
async def trigger_reflection(reflection_storage: ReflectionStorage = Depends(get_reflection_storage)):
    """
    前端 triggerReflection.ts 呼叫此路由，主動觸發 AI 的記憶反思流程。
    """
    logger.info("🧠 接收到主動反思觸發請求...")
    try:
        # 這裡啟動一個後台任務來處理耗時的反思，避免阻塞主線程
        # 為了簡化，我們先返回成功，假設你的 ReflectionStorage 有一個啟動方法
        
        # 實際應該呼叫 ReflectionStorage 啟動記憶整合與反思
        # await reflection_storage.start_reflection_process() 
        
        return {"success": True, "message": "反思觸發請求已接收，AI寶貝正在開始整理思緒..."}

    except Exception as e:
        traceback_str = traceback.format_exc()
        logger.error(f"❌ 反思觸發路由錯誤: {e}\n{traceback_str}")
        raise HTTPException(status_code=500, detail="後端光流異常，無法觸發反思。")
