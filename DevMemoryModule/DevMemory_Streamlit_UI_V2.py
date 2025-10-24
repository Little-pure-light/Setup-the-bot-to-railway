"""
XiaoChenGuang 開發者記憶助手 - Streamlit UI V2
完全重構版本 - 解決所有已知問題

修復內容：
1. ✅ 加入 dotenv 環境變數載入
2. ✅ 所有 dict 存取改用 .get()（防止 KeyError）
3. ✅ 完整的錯誤處理和友善提示
4. ✅ 優化 UI 卡片顯示
5. ✅ 測試三大功能（記錄/搜尋/背景包）
"""

import streamlit as st
import os
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
    st.error(f"❌ 套件導入失敗：{e}")
    st.info("請執行：pip install supabase openai python-dotenv streamlit")
    st.stop()

# ============================================
# 配置
# ============================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ============================================
# 初始化客戶端（加入錯誤處理）
# ============================================
@st.cache_resource
def init_clients():
    """初始化 Supabase 和 OpenAI 客戶端"""
    try:
        if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY]):
            missing = []
            if not SUPABASE_URL: missing.append("SUPABASE_URL")
            if not SUPABASE_KEY: missing.append("SUPABASE_ANON_KEY")
            if not OPENAI_API_KEY: missing.append("OPENAI_API_KEY")
            
            raise ValueError(f"缺少環境變數：{', '.join(missing)}")
        
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        return supabase, openai_client
    
    except Exception as e:
        st.error(f"❌ 客戶端初始化失敗：{e}")
        st.stop()

# ============================================
# 核心功能（加入完整錯誤處理）
# ============================================

def generate_embedding(openai_client: OpenAI, text: str):
    """生成文本向量嵌入"""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]  # 限制長度
        )
        return response.data[0].embedding
    except Exception as e:
        st.error(f"❌ 向量生成失敗：{e}")
        return None

def save_dev_log(
    supabase: Client,
    openai_client: OpenAI,
    phase: str,
    module: str,
    ai_model: str,
    topic: str,
    question: str,
    answer: str,
    tags: list
):
    """儲存開發日誌"""
    try:
        # 1. 生成摘要
        q_summary = question[:50] + ("..." if len(question) > 50 else "")
        a_summary = answer[:100] + ("..." if len(answer) > 100 else "")
        summary = f"問：{q_summary} 答：{a_summary}"
        
        # 2. 計算重要性
        importance = 0.5
        if phase in ["Phase3", "Phase4", "Phase5"]:
            importance += 0.3
        if len(answer) > 500:
            importance += 0.2
        
        # 3. 生成向量
        combined = f"{topic} {question} {answer}"
        embedding = generate_embedding(openai_client, combined)
        
        if not embedding:
            return False, "向量生成失敗"
        
        # 4. 儲存資料
        data = {
            "phase": phase,
            "module": module,
            "ai_model": ai_model,
            "topic": topic,
            "user_question": question,
            "ai_response": answer,
            "summary": summary,
            "embedding": embedding,
            "importance_score": min(importance, 1.0),
            "tags": tags
        }
        
        result = supabase.table("dev_logs").insert(data).execute()
        
        # 5. 檢查結果（使用 .get() 防止 KeyError）
        if result.data and len(result.data) > 0:
            log_id = result.data[0].get("id", "unknown")
            return True, str(log_id)
        else:
            return False, "資料儲存失敗"
    
    except Exception as e:
        return False, f"儲存錯誤：{str(e)}"

def search_dev_logs(supabase: Client, openai_client: OpenAI, query: str, limit: int = 5):
    """搜尋開發日誌"""
    try:
        # 1. 生成查詢向量
        query_embedding = generate_embedding(openai_client, query)
        
        if not query_embedding:
            return []
        
        # 2. 呼叫 RPC 函數（修正版本 - 只傳遞兩個參數）
        result = supabase.rpc(
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
                    "created_at": log.get("created_at", ""),
                    "phase": log.get("phase", "未知"),
                    "module": log.get("module", "未知"),
                    "ai_model": log.get("ai_model", "未知"),
                    "topic": log.get("topic", "無主題"),
                    "user_question": log.get("user_question", ""),
                    "ai_response": log.get("ai_response", ""),
                    "summary": log.get("summary", ""),
                    "similarity": log.get("similarity", 0.0)
                }
                for log in result.data
            ]
        else:
            return []
    
    except Exception as e:
        st.error(f"❌ 搜尋錯誤：{str(e)}")
        return []

def generate_context_pack(supabase: Client, phase=None, module=None):
    """生成專案背景包"""
    try:
        # 方案 1：使用 RPC 函數
        result = supabase.rpc(
            "generate_project_context",
            {
                "target_phase": phase,
                "target_module": module,
                "max_logs": 10
            }
        ).execute()
        
        if result.data:
            return True, result.data
        else:
            # 方案 2：手動生成
            return manual_generate_context(supabase, phase, module)
    
    except Exception as e:
        # 降級為手動生成
        return manual_generate_context(supabase, phase, module)

def manual_generate_context(supabase: Client, phase=None, module=None):
    """手動生成背景包（降級方案）"""
    try:
        # 查詢最近記錄
        query = supabase.table("dev_logs").select("*")
        
        if phase:
            query = query.eq("phase", phase)
        if module:
            query = query.eq("module", module)
        
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
                phase_tag = log.get("phase", "未知")
                topic = log.get("topic", "無主題")
                summary = log.get("summary", "")[:80]
                
                context += f"{i}. {date} [{phase_tag}] {topic}\n"
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
        return True, context
    
    except Exception as e:
        return False, f"❌ 背景包生成失敗：{e}"

# ============================================
# Streamlit UI
# ============================================

def main():
    st.set_page_config(
        page_title="🧠 XiaoChenGuang 開發者記憶助手",
        page_icon="🧠",
        layout="wide"
    )
    
    # 自訂 CSS（優化視覺效果）
    st.markdown("""
    <style>
    .big-font {
        font-size: 20px !important;
        font-weight: bold;
    }
    .card {
        padding: 20px;
        border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("🧠 XiaoChenGuang 開發者記憶助手")
    st.markdown("**讓你的 AI 不再失憶！快速記錄開發對話，一鍵喚醒 AI 記憶**")
    
    # 檢查環境變數
    if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY]):
        st.error("⚠️ 缺少環境變數！")
        st.info("""
        請在 Replit Secrets 中設定：
        - SUPABASE_URL
        - SUPABASE_ANON_KEY
        - OPENAI_API_KEY
        """)
        st.stop()
    
    # 初始化客戶端
    supabase, openai_client = init_clients()
    
    # 側邊欄
    st.sidebar.title("🎯 功能選單")
    mode = st.sidebar.radio(
        "選擇功能",
        ["📝 快速記錄", "🔍 搜尋記憶", "📦 生成背景包"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("🌌 XiaoChenGuang 靈魂孵化器")
    st.sidebar.caption("讓 AI 記住你的開發歷程")
    
    # ============================================
    # 功能 1：快速記錄
    # ============================================
    if mode == "📝 快速記錄":
        st.header("📝 快速記錄開發對話")
        st.markdown("跟 AI 討論完專案後，立刻記錄重點！")
        
        col1, col2 = st.columns(2)
        
        with col1:
            phase = st.selectbox(
                "階段",
                ["Phase1", "Phase2", "Phase3", "Phase4", "Phase5", "其他"]
            )
            
            module = st.selectbox(
                "模組",
                ["記憶模組", "反思模組", "行為調節模組", "知識庫", "微調模組", "情感檢測", "提示詞引擎", "通用"]
            )
        
        with col2:
            ai_model = st.selectbox(
                "AI 模型",
                ["GPT-4", "GPT-4o", "GPT-4o-mini", "Claude-3.5-Sonnet", "Claude-3-Opus", "Gemini-Pro", "Gemini-Flash", "其他"]
            )
            
            topic = st.text_input("討論主題", placeholder="例如：反思循環測試方法")
        
        question = st.text_area(
            "你的問題",
            placeholder="你問 AI 的問題...",
            height=150
        )
        
        answer = st.text_area(
            "AI 的回答",
            placeholder="AI 給你的回答...",
            height=250
        )
        
        tags_input = st.text_input(
            "標籤（用逗號分隔，可選）",
            placeholder="測試,bug修復,Phase3"
        )
        
        if st.button("💾 儲存記錄", type="primary", use_container_width=True):
            # 驗證輸入
            if not all([topic, question, answer]):
                st.error("❌ 請填寫所有必填欄位（主題、問題、回答）！")
            else:
                tags = [t.strip() for t in tags_input.split(",")] if tags_input else []
                
                with st.spinner("儲存中..."):
                    success, result = save_dev_log(
                        supabase, openai_client, phase, module, ai_model,
                        topic, question, answer, tags
                    )
                
                if success:
                    st.success(f"✅ 儲存成功！記錄 ID: {result}")
                    st.balloons()
                else:
                    st.error(f"❌ 儲存失敗：{result}")
    
    # ============================================
    # 功能 2：搜尋記憶
    # ============================================
    elif mode == "🔍 搜尋記憶":
        st.header("🔍 搜尋開發記憶")
        st.markdown("用關鍵字或問題搜尋相關的開發記錄")
        
        query = st.text_input(
            "搜尋問題",
            placeholder="例如：反思模組如何測試？",
            key="search_query"
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            limit = st.slider("返回數量", 1, 10, 5)
        with col2:
            search_button = st.button("🔍 搜尋", type="primary", use_container_width=True)
        
        if search_button:
            if not query:
                st.error("❌ 請輸入搜尋問題！")
            else:
                with st.spinner("搜尋中..."):
                    results = search_dev_logs(supabase, openai_client, query, limit)
                
                if results:
                    st.success(f"✅ 找到 {len(results)} 條相關記錄")
                    
                    for i, log in enumerate(results, 1):
                        # 安全取值（使用 .get()）
                        topic = log.get("topic", "無主題")
                        phase = log.get("phase", "未知")
                        similarity = log.get("similarity", 0.0)
                        date = log.get("created_at", "")[:10]
                        module = log.get("module", "未知")
                        ai_model = log.get("ai_model", "未知")
                        summary = log.get("summary", "")
                        user_q = log.get("user_question", "")
                        ai_a = log.get("ai_response", "")
                        
                        # 卡片式顯示（優化 UI）
                        with st.expander(
                            f"📌 {i}. {topic} ({phase}) - 相似度: {similarity:.2%}",
                            expanded=(i == 1)  # 第一條預設展開
                        ):
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.caption(f"📅 日期：{date}")
                            with col_b:
                                st.caption(f"🧩 模組：{module}")
                            with col_c:
                                st.caption(f"🤖 AI：{ai_model}")
                            
                            st.markdown("---")
                            
                            if summary:
                                st.info(f"📝 摘要：{summary}")
                            
                            st.markdown("**💬 問題：**")
                            st.code(user_q, language=None)
                            
                            st.markdown("**✨ 回答：**")
                            st.code(ai_a, language=None)
                else:
                    st.warning("⚠️ 未找到相關記錄")
    
    # ============================================
    # 功能 3：生成背景包
    # ============================================
    elif mode == "📦 生成背景包":
        st.header("📦 生成 AI 記憶喚醒包")
        st.markdown("一鍵生成專案背景摘要，貼給新 AI 立刻喚醒記憶！")
        
        col1, col2 = st.columns(2)
        
        with col1:
            filter_phase = st.selectbox(
                "篩選階段（可選）",
                ["全部", "Phase1", "Phase2", "Phase3", "Phase4", "Phase5"]
            )
        
        with col2:
            filter_module = st.selectbox(
                "篩選模組（可選）",
                ["全部", "記憶模組", "反思模組", "行為調節模組", "知識庫", "其他"]
            )
        
        if st.button("🚀 生成背景包", type="primary", use_container_width=True):
            with st.spinner("生成中..."):
                phase = None if filter_phase == "全部" else filter_phase
                module = None if filter_module == "全部" else filter_module
                
                success, context = generate_context_pack(supabase, phase, module)
            
            if success:
                st.success("✅ 生成完成！")
                st.markdown("---")
                st.markdown("### 📋 複製下面的背景包，貼給任何 AI：")
                
                st.text_area(
                    "專案背景包",
                    value=context,
                    height=500,
                    key="context_pack"
                )
                
                st.info("💡 **使用方式：** 複製上面的文字 → 貼給 ChatGPT/Claude/Gemini → AI 就能記起你的專案了！")
            else:
                st.error(f"❌ {context}")
    
    # 頁尾
    st.markdown("---")
    st.caption("🌌 由 XiaoChenGuang 靈魂孵化器提供支援 | V2.0 重構版")


if __name__ == "__main__":
    main()
