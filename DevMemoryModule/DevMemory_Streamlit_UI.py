"""
開發者記憶助手 - Streamlit 簡易介面
用途：快速記錄開發對話 + 生成 AI 背景包
位置：可以放在 SemanticMemoryUploaderMini/dev_memory_helper.py

完美契合：
- 使用你現有的 Supabase 連接
- 使用你現有的 OpenAI API
- 可以跟現有的 Streamlit 上傳器整合
"""

import streamlit as st
import os
from datetime import datetime
from supabase import create_client
import openai

# ============================================
# 配置
# ============================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ============================================
# 初始化
# ============================================
@st.cache_resource
def init_clients():
    """初始化 Supabase 和 OpenAI 客戶端"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    openai.api_key = OPENAI_API_KEY
    return supabase

# ============================================
# 核心功能
# ============================================

def generate_embedding(text: str):
    """生成文本向量嵌入"""
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def save_dev_log(supabase, phase, module, ai_model, topic, question, answer, tags):
    """儲存開發日誌"""
    try:
        # 生成摘要
        q_summary = question[:50] + ("..." if len(question) > 50 else "")
        a_summary = answer[:100] + ("..." if len(answer) > 100 else "")
        summary = f"問：{q_summary} 答：{a_summary}"
        
        # 計算重要性
        importance = 0.5
        if phase in ["Phase3", "Phase4"]:
            importance += 0.3
        if len(answer) > 500:
            importance += 0.2
        
        # 生成向量
        combined = f"{topic} {question} {answer}"
        embedding = generate_embedding(combined)
        
        # 儲存
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
        return True, result.data[0]["id"]
    
    except Exception as e:
        return False, str(e)

def search_dev_logs(supabase, query, limit=5):
    """搜尋開發日誌"""
    try:
        # 生成查詢向量
        query_embedding = generate_embedding(query)
        
        # 呼叫 RPC 函數
        result = supabase.rpc(
            "match_dev_logs",
            {
                "query_embedding": query_embedding,
                "match_count": limit
            }
        ).execute()
        
        return result.data
    except Exception as e:
        st.error(f"搜尋錯誤：{e}")
        return []

def generate_context_pack(supabase, phase=None, module=None):
    """生成專案背景包"""
    try:
        # 查詢最近記錄
        query = supabase.table("dev_logs").select("*")
        
        if phase:
            query = query.eq("phase", phase)
        if module:
            query = query.eq("module", module)
        
        result = query.order("created_at", desc=True).limit(10).execute()
        logs = result.data
        
        # 組合文本
        context = f"""📦 XiaoChenGuang 專案背景包
生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}

【專案概述】
數位靈魂孵化器 - XiaoChenGuang AI 系統
技術棧：FastAPI + Vue 3 + Supabase + OpenAI
核心模組：
- 記憶系統（向量嵌入 + pgvector + Redis）
- 反思模組（反推果因法則）
- 人格學習引擎（動態特質調整）
- 情感檢測系統（9種情緒類型）
- 提示詞引擎（動態 Prompt 生成）

【最近開發記錄】
"""
        
        for log in logs:
            date = log["created_at"][:10]
            phase_tag = log.get("phase", "通用")
            topic = log.get("topic", "無主題")
            summary = log.get("summary", "")[:80]
            
            context += f"- {date} [{phase_tag}] {topic}\n"
            context += f"  {summary}...\n"
        
        context += """
【使用說明】
1. 複製上面的背景包
2. 貼給任何 AI（ChatGPT/Claude/Gemini）
3. AI 就能立刻了解專案背景！
4. 然後問你的問題，AI 會給出更精準的建議

---
由 XiaoChenGuang 開發者記憶助手生成
"""
        return context
    
    except Exception as e:
        return f"生成錯誤：{e}"

# ============================================
# Streamlit UI
# ============================================

def main():
    st.set_page_config(
        page_title="🧠 開發者記憶助手",
        page_icon="🧠",
        layout="wide"
    )
    
    st.title("🧠 XiaoChenGuang 開發者記憶助手")
    st.markdown("**讓你的 AI 不再失憶！快速記錄開發對話，一鍵喚醒 AI 記憶**")
    
    # 檢查環境變數
    if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY]):
        st.error("⚠️ 缺少環境變數！請設定 SUPABASE_URL, SUPABASE_ANON_KEY, OPENAI_API_KEY")
        return
    
    # 初始化客戶端
    supabase = init_clients()
    
    # 側邊欄：功能選擇
    st.sidebar.title("🎯 功能選單")
    mode = st.sidebar.radio(
        "選擇功能",
        ["📝 快速記錄", "🔍 搜尋記憶", "📦 生成背景包"]
    )
    
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
                ["GPT-4", "GPT-4o", "Claude-3.5", "Claude-3", "Gemini-Pro", "其他"]
            )
            
            topic = st.text_input("討論主題", placeholder="例如：反思循環測試方法")
        
        question = st.text_area(
            "你的問題",
            placeholder="你問 AI 的問題...",
            height=100
        )
        
        answer = st.text_area(
            "AI 的回答",
            placeholder="AI 給你的回答...",
            height=200
        )
        
        tags_input = st.text_input(
            "標籤（用逗號分隔）",
            placeholder="測試,bug修復,Phase3"
        )
        
        if st.button("💾 儲存記錄", type="primary", use_container_width=True):
            if not all([topic, question, answer]):
                st.error("請填寫所有必填欄位！")
            else:
                tags = [t.strip() for t in tags_input.split(",")] if tags_input else []
                
                with st.spinner("儲存中..."):
                    success, result = save_dev_log(
                        supabase, phase, module, ai_model, 
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
            if st.button("🔍 搜尋", type="primary", use_container_width=True):
                if query:
                    with st.spinner("搜尋中..."):
                        results = search_dev_logs(supabase, query, limit)
                    
                    if results:
                        st.success(f"找到 {len(results)} 條相關記錄")
                        
                        for i, log in enumerate(results, 1):
                            with st.expander(f"📌 {i}. {log['topic']} ({log['phase']}) - 相似度: {log['similarity']:.2%}"):
                                st.markdown(f"**日期：** {log['created_at'][:10]}")
                                st.markdown(f"**模組：** {log['module']}")
                                st.markdown(f"**摘要：** {log['summary']}")
                                
                                st.markdown("---")
                                st.markdown("**問題：**")
                                st.info(log['user_question'])
                                
                                st.markdown("**回答：**")
                                st.success(log['ai_response'])
                                
                                # 一鍵複製
                                copy_text = f"問：{log['user_question']}\n\n答：{log['ai_response']}"
                                st.code(copy_text, language=None)
                    else:
                        st.warning("沒有找到相關記錄")
                else:
                    st.error("請輸入搜尋問題！")
    
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
                
                context = generate_context_pack(supabase, phase, module)
            
            st.success("✅ 生成完成！")
            st.markdown("---")
            st.markdown("### 📋 複製下面的背景包，貼給任何 AI：")
            
            st.text_area(
                "專案背景包",
                value=context,
                height=400,
                key="context_pack"
            )
            
            st.info("💡 使用方式：複製上面的文字 → 貼給 ChatGPT/Claude/Gemini → AI 就能記起你的專案了！")
    
    # 頁尾
    st.markdown("---")
    st.caption("🌌 由 XiaoChenGuang 靈魂孵化器提供支援 | 讓 AI 記住你的開發歷程")


if __name__ == "__main__":
    main()
