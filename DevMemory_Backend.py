"""
開發者記憶模組 - 後端處理器
用途：整合到你現有的 XiaoChenGuang 靈魂孵化器系統
位置：放在 backend/modules/dev_memory.py

完美契合你現有的架構：
- 使用相同的 Supabase 連接
- 使用相同的 OpenAI embeddings
- API 風格跟現有的 memory_router.py 一致
"""

from typing import Optional, List, Dict
from datetime import datetime
import openai
from supabase import Client


class DevMemoryModule:
    """
    開發者記憶模組
    
    功能：
    1. 儲存開發對話（你跟各種 AI 的討論）
    2. 語義搜尋（根據問題找相關記錄）
    3. 生成專案背景包（喚醒新 AI 的記憶）
    """
    
    def __init__(self, supabase_client: Client, openai_api_key: str):
        """
        初始化模組
        
        參數：
            supabase_client: Supabase 客戶端（使用現有的連接）
            openai_api_key: OpenAI API 金鑰（使用現有的）
        """
        self.supabase = supabase_client
        openai.api_key = openai_api_key
        self.embedding_model = "text-embedding-3-small"  # 跟你的 memory_system.py 一樣
    
    async def save_dev_log(
        self,
        phase: str,
        module: str,
        ai_model: str,
        topic: str,
        user_question: str,
        ai_response: str,
        tags: Optional[List[str]] = None,
        related_files: Optional[List[str]] = None
    ) -> Dict:
        """
        儲存開發日誌
        
        參數：
            phase: 階段（Phase1/Phase2/Phase3...）
            module: 模組名稱（記憶模組/反思模組...）
            ai_model: AI 模型（GPT-4/Claude/Gemini）
            topic: 討論主題
            user_question: 你的問題
            ai_response: AI 的回答
            tags: 標籤列表
            related_files: 相關檔案路徑
        
        回傳：
            儲存結果
        """
        try:
            # 1. 生成摘要（簡單規則，不花錢）
            summary = self._generate_summary(user_question, ai_response)
            
            # 2. 計算重要性評分
            importance = self._calculate_importance(user_question, ai_response, phase)
            
            # 3. 生成向量嵌入
            combined_text = f"{topic} {user_question} {ai_response}"
            embedding = await self._get_embedding(combined_text)
            
            # 4. 儲存到 Supabase
            data = {
                "phase": phase,
                "module": module,
                "ai_model": ai_model,
                "topic": topic,
                "user_question": user_question,
                "ai_response": ai_response,
                "summary": summary,
                "embedding": embedding,
                "importance_score": importance,
                "tags": tags or [],
                "related_files": related_files or []
            }
            
            result = self.supabase.table("dev_logs").insert(data).execute()
            
            return {
                "success": True,
                "log_id": result.data[0]["id"],
                "summary": summary,
                "importance": importance
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_dev_logs(
        self,
        query: str,
        limit: int = 5,
        filter_phase: Optional[str] = None,
        filter_module: Optional[str] = None
    ) -> List[Dict]:
        """
        語義搜尋開發日誌
        
        參數：
            query: 搜尋問題（例如：「反思模組如何測試？」）
            limit: 返回數量
            filter_phase: 篩選階段
            filter_module: 篩選模組
        
        回傳：
            相關日誌列表
        """
        try:
            # 1. 將問題轉換為向量
            query_embedding = await self._get_embedding(query)
            
            # 2. 呼叫 Supabase RPC 函數
            result = self.supabase.rpc(
                "match_dev_logs",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "filter_phase": filter_phase,
                    "filter_module": filter_module
                }
            ).execute()
            
            return result.data
        
        except Exception as e:
            print(f"搜尋錯誤: {e}")
            return []
    
    async def generate_context_pack(
        self,
        target_phase: Optional[str] = None,
        target_module: Optional[str] = None,
        include_recent: int = 10
    ) -> str:
        """
        生成專案背景包（給新 AI 看的）
        
        參數：
            target_phase: 目標階段（None = 全部）
            target_module: 目標模組（None = 全部）
            include_recent: 包含最近 N 筆記錄
        
        回傳：
            格式化的背景包文本
        """
        try:
            # 呼叫 Supabase RPC 函數
            result = self.supabase.rpc(
                "generate_project_context",
                {
                    "target_phase": target_phase,
                    "target_module": target_module
                }
            ).execute()
            
            return result.data
        
        except Exception as e:
            # 降級方案：手動生成
            return self._manual_generate_context(target_phase, target_module, include_recent)
    
    def _generate_summary(self, question: str, answer: str) -> str:
        """
        生成摘要（簡單規則，不花錢）
        
        規則：
        1. 提取問題的前 50 字
        2. 提取答案的前 100 字
        3. 組合成摘要
        """
        q_summary = question[:50] + ("..." if len(question) > 50 else "")
        a_summary = answer[:100] + ("..." if len(answer) > 100 else "")
        
        return f"問：{q_summary} 答：{a_summary}"
    
    def _calculate_importance(self, question: str, answer: str, phase: str) -> float:
        """
        計算重要性評分（0-1）
        
        規則：
        1. Phase 3/4 = 高重要性（0.8-1.0）
        2. 長回答 = 較重要（>500字 +0.2）
        3. 包含關鍵字 = 較重要（bug/錯誤/測試 +0.1）
        """
        score = 0.5  # 基礎分數
        
        # Phase 加權
        if phase in ["Phase3", "Phase4"]:
            score += 0.3
        
        # 回答長度
        if len(answer) > 500:
            score += 0.2
        
        # 關鍵字檢測
        keywords = ["bug", "錯誤", "測試", "修復", "問題", "失敗"]
        if any(kw in question.lower() or kw in answer.lower() for kw in keywords):
            score += 0.1
        
        return min(score, 1.0)  # 上限 1.0
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        生成文本向量嵌入
        
        使用 OpenAI text-embedding-3-small（跟你的 memory_system.py 一樣）
        """
        response = openai.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def _manual_generate_context(
        self,
        target_phase: Optional[str],
        target_module: Optional[str],
        limit: int
    ) -> str:
        """
        手動生成背景包（降級方案）
        """
        # 查詢最近記錄
        query = self.supabase.table("dev_logs").select("*")
        
        if target_phase:
            query = query.eq("phase", target_phase)
        if target_module:
            query = query.eq("module", target_module)
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        logs = result.data
        
        # 組合文本
        context = f"📦 XiaoChenGuang 專案背景包\n"
        context += f"生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        
        context += "【專案概述】\n"
        context += "數位靈魂孵化器 - XiaoChenGuang AI 系統\n"
        context += "- 記憶模組（向量嵌入 + pgvector）\n"
        context += "- 反思模組（反推果因法則）\n"
        context += "- 行為調節模組（人格向量）\n"
        context += "- 情感檢測系統（9種情緒）\n\n"
        
        context += "【最近開發記錄】\n"
        for log in logs:
            date = log["created_at"][:10]
            phase = log.get("phase", "通用")
            topic = log.get("topic", "無主題")
            summary = log.get("summary", "")[:100]
            
            context += f"- {date} [{phase}] {topic}\n"
            context += f"  摘要：{summary}...\n"
        
        context += "\n【使用說明】\n"
        context += "請將此背景包複製貼給任何 AI，AI 就能了解專案背景！\n"
        
        return context


# ============================================
# FastAPI 路由範例（整合到你的 backend/main.py）
# ============================================

"""
from fastapi import APIRouter, Depends
from backend.modules.dev_memory import DevMemoryModule
from backend.supabase_handler import get_supabase_client

dev_router = APIRouter(prefix="/api/dev-memory", tags=["開發者記憶"])

@dev_router.post("/save")
async def save_dev_log(
    phase: str,
    module: str,
    ai_model: str,
    topic: str,
    user_question: str,
    ai_response: str,
    tags: List[str] = None
):
    dev_memory = DevMemoryModule(
        supabase_client=get_supabase_client(),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    result = await dev_memory.save_dev_log(
        phase=phase,
        module=module,
        ai_model=ai_model,
        topic=topic,
        user_question=user_question,
        ai_response=ai_response,
        tags=tags
    )
    
    return result

@dev_router.get("/search")
async def search_logs(
    query: str,
    limit: int = 5,
    phase: str = None,
    module: str = None
):
    dev_memory = DevMemoryModule(...)
    results = await dev_memory.search_dev_logs(
        query=query,
        limit=limit,
        filter_phase=phase,
        filter_module=module
    )
    return results

@dev_router.get("/context-pack")
async def get_context_pack(
    phase: str = None,
    module: str = None
):
    dev_memory = DevMemoryModule(...)
    context = await dev_memory.generate_context_pack(
        target_phase=phase,
        target_module=module
    )
    return {"context": context}
"""
