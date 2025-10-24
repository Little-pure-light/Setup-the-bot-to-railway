"""
XiaoChenGuang 開發者記憶助手 - 後端模組 V2
完全重構版本 - 解決所有已知問題

修復內容：
1. ✅ 加入 dotenv 環境變數載入
2. ✅ 修正 RPC 函數調用（統一簽章）
3. ✅ 完整的錯誤處理（try/except）
4. ✅ 使用 .get() 防止 KeyError
5. ✅ 統一使用 text-embedding-3-small
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# ============================================
# 環境變數載入（修復問題 1）
# ============================================
load_dotenv()  # 強制載入 .env 檔案

# ============================================
# 延遲導入（避免環境變數未載入）
# ============================================
try:
    from supabase import create_client, Client
    from openai import OpenAI
except ImportError as e:
    print(f"❌ 套件導入錯誤：{e}")
    print("請執行：pip install supabase openai python-dotenv")
    raise


class DevMemoryBackend:
    """
    開發者記憶後端處理器
    
    功能：
    1. 儲存開發對話
    2. 語義搜尋記錄
    3. 生成專案背景包
    
    完美契合 XiaoChenGuang 靈魂孵化器架構
    """
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        openai_api_key: Optional[str] = None
    ):
        """
        初始化後端模組
        
        參數：
            supabase_url: Supabase URL（預設從環境變數讀取）
            supabase_key: Supabase Anon Key（預設從環境變數讀取）
            openai_api_key: OpenAI API Key（預設從環境變數讀取）
        """
        # 環境變數讀取（加入預設值處理）
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_ANON_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        # 驗證環境變數
        self._validate_env_vars()
        
        # 初始化客戶端
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            self.embedding_model = "text-embedding-3-small"  # 統一使用此模型
        except Exception as e:
            raise RuntimeError(f"❌ 客戶端初始化失敗：{e}")
    
    def _validate_env_vars(self) -> None:
        """驗證必要的環境變數是否存在"""
        missing_vars = []
        
        if not self.supabase_url:
            missing_vars.append("SUPABASE_URL")
        if not self.supabase_key:
            missing_vars.append("SUPABASE_ANON_KEY")
        if not self.openai_api_key:
            missing_vars.append("OPENAI_API_KEY")
        
        if missing_vars:
            raise ValueError(
                f"❌ 缺少環境變數：{', '.join(missing_vars)}\n"
                f"請在 Replit Secrets 或 .env 檔案中設定"
            )
    
    def save_dev_log(
        self,
        phase: str,
        module: str,
        ai_model: str,
        topic: str,
        user_question: str,
        ai_response: str,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        儲存開發日誌
        
        參數：
            phase: 階段（Phase1/Phase2...）
            module: 模組名稱
            ai_model: AI 模型
            topic: 討論主題
            user_question: 用戶問題
            ai_response: AI 回答
            tags: 標籤列表
        
        回傳：
            {"success": bool, "log_id": str, "summary": str} 或錯誤訊息
        """
        try:
            # 1. 生成摘要
            summary = self._generate_summary(user_question, ai_response)
            
            # 2. 計算重要性
            importance = self._calculate_importance(user_question, ai_response, phase)
            
            # 3. 生成向量嵌入
            combined_text = f"{topic} {user_question} {ai_response}"
            embedding = self._get_embedding(combined_text)
            
            if not embedding:
                return {
                    "success": False,
                    "error": "向量生成失敗"
                }
            
            # 4. 準備資料
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
                "tags": tags or []
            }
            
            # 5. 儲存到 Supabase
            result = self.supabase.table("dev_logs").insert(data).execute()
            
            # 6. 檢查結果（使用 .get() 防止 KeyError）
            if result.data and len(result.data) > 0:
                log_id = result.data[0].get("id", "unknown")
                return {
                    "success": True,
                    "log_id": str(log_id),
                    "summary": summary,
                    "importance": importance
                }
            else:
                return {
                    "success": False,
                    "error": "資料儲存失敗，無回傳結果"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"儲存錯誤：{str(e)}"
            }
    
    def search_memory(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        語義搜尋開發記錄
        
        參數：
            query: 搜尋問題
            limit: 返回數量
        
        回傳：
            相關記錄列表（包含相似度分數）
        """
        try:
            # 1. 生成查詢向量
            query_embedding = self._get_embedding(query)
            
            if not query_embedding:
                return []
            
            # 2. 呼叫 RPC 函數（修正版本 - 只傳遞兩個參數）
            result = self.supabase.rpc(
                "match_dev_logs",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit
                }
            ).execute()
            
            # 3. 處理結果（使用 .get() 防止 KeyError）
            if result.data:
                return [
                    {
                        "id": log.get("id"),
                        "created_at": log.get("created_at"),
                        "phase": log.get("phase", "未知"),
                        "module": log.get("module", "未知"),
                        "ai_model": log.get("ai_model", "未知"),
                        "topic": log.get("topic", "無主題"),
                        "user_question": log.get("user_question", ""),
                        "ai_response": log.get("ai_response", ""),
                        "summary": log.get("summary", ""),
                        "similarity": round(log.get("similarity", 0.0), 4)
                    }
                    for log in result.data
                ]
            else:
                return []
        
        except Exception as e:
            print(f"❌ 搜尋錯誤：{e}")
            return []
    
    def generate_context_pack(
        self,
        target_phase: Optional[str] = None,
        target_module: Optional[str] = None
    ) -> str:
        """
        生成專案背景包
        
        參數：
            target_phase: 篩選階段（None = 全部）
            target_module: 篩選模組（None = 全部）
        
        回傳：
            格式化的背景包文本
        """
        try:
            # 方案 1：使用 RPC 函數生成（推薦）
            result = self.supabase.rpc(
                "generate_project_context",
                {
                    "target_phase": target_phase,
                    "target_module": target_module,
                    "max_logs": 10
                }
            ).execute()
            
            if result.data:
                return result.data
            else:
                # 方案 2：手動生成（降級方案）
                return self._manual_generate_context(target_phase, target_module)
        
        except Exception as e:
            print(f"⚠️ RPC 生成失敗，使用手動方案：{e}")
            return self._manual_generate_context(target_phase, target_module)
    
    def _generate_summary(self, question: str, answer: str) -> str:
        """生成簡單摘要（不花錢）"""
        q_summary = question[:50] + ("..." if len(question) > 50 else "")
        a_summary = answer[:100] + ("..." if len(answer) > 100 else "")
        return f"問：{q_summary} 答：{a_summary}"
    
    def _calculate_importance(self, question: str, answer: str, phase: str) -> float:
        """計算重要性評分（0-1）"""
        score = 0.5
        
        # Phase 加權
        if phase in ["Phase3", "Phase4", "Phase5"]:
            score += 0.3
        elif phase in ["Phase2"]:
            score += 0.1
        
        # 回答長度
        if len(answer) > 500:
            score += 0.2
        elif len(answer) > 200:
            score += 0.1
        
        # 關鍵字檢測
        keywords = ["bug", "錯誤", "測試", "修復", "問題", "失敗", "重要", "關鍵"]
        text_lower = (question + answer).lower()
        if any(kw in text_lower for kw in keywords):
            score += 0.1
        
        return min(score, 1.0)
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        生成文本向量嵌入
        
        使用 OpenAI text-embedding-3-small（1536 維）
        """
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text[:8000]  # 限制長度避免超出 token 限制
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ 向量生成錯誤：{e}")
            return None
    
    def _manual_generate_context(
        self,
        target_phase: Optional[str],
        target_module: Optional[str]
    ) -> str:
        """手動生成背景包（降級方案）"""
        try:
            # 查詢最近記錄
            query = self.supabase.table("dev_logs").select("*")
            
            if target_phase:
                query = query.eq("phase", target_phase)
            if target_module:
                query = query.eq("module", target_module)
            
            result = query.order("created_at", desc=True).limit(10).execute()
            logs = result.data or []
            
            # 組合文本
            context = f"""📦 XiaoChenGuang 專案背景包
生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

【專案概述】
數位靈魂孵化器 - XiaoChenGuang AI 系統
技術棧：FastAPI + Vue 3 + Supabase + OpenAI + Redis
核心模組：
  • 記憶系統（向量嵌入 + pgvector）
  • 反思模組（反推果因法則）
  • 人格學習引擎（動態特質調整）
  • 情感檢測系統（9種情緒類型）
  • 提示詞引擎（動態 Prompt 生成）

【最近開發記錄】
"""
            
            if logs:
                for i, log in enumerate(logs, 1):
                    date = log.get("created_at", "")[:10]
                    phase = log.get("phase", "未知")
                    topic = log.get("topic", "無主題")
                    summary = log.get("summary", "")[:80]
                    
                    context += f"{i}. {date} [{phase}] {topic}\n"
                    context += f"   摘要：{summary}...\n\n"
            else:
                context += "（目前尚無開發記錄）\n\n"
            
            context += """【使用說明】
1. 複製上面的背景包
2. 貼給任何 AI（ChatGPT/Claude/Gemini）
3. AI 就能立刻了解專案背景！
4. 然後問你的問題，AI 會給出更精準的建議

---
由 XiaoChenGuang 開發者記憶助手生成
"""
            
            return context
        
        except Exception as e:
            return f"❌ 背景包生成失敗：{e}"


# ============================================
# 使用範例
# ============================================

if __name__ == "__main__":
    # 初始化
    backend = DevMemoryBackend()
    
    # 測試儲存
    result = backend.save_dev_log(
        phase="Phase1",
        module="測試模組",
        ai_model="GPT-4",
        topic="後端測試",
        user_question="這個後端模組能正常運作嗎？",
        ai_response="是的，所有功能都已正確實作並加入完整的錯誤處理。",
        tags=["測試", "後端"]
    )
    print("儲存結果：", result)
    
    # 測試搜尋
    search_results = backend.search_memory("測試", limit=3)
    print(f"\n搜尋結果（找到 {len(search_results)} 筆）：")
    for log in search_results:
        print(f"  - {log['topic']} (相似度: {log['similarity']:.2%})")
    
    # 測試背景包
    context = backend.generate_context_pack()
    print("\n背景包預覽：")
    print(context[:300], "...")
