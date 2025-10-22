# 🧠 開發者記憶模組 - XiaoChenGuang 急救樂高

## 📦 這個資料夾包含什麼？

這是專門為 **XiaoChenGuang 靈魂孵化器** 設計的**開發者記憶系統**！

### 核心檔案：

1. **`DevMemory_Supabase_Schema.sql`** 📊
   - Supabase 資料表建立腳本
   - 在 Supabase SQL Editor 執行一次即可

2. **`DevMemory_Backend.py`** 🔧
   - Python 後端處理模組
   - 可整合進你的 FastAPI 系統

3. **`DevMemory_Streamlit_UI.py`** 🎨
   - Streamlit 使用者介面
   - 3 大功能：快速記錄 / 搜尋記憶 / 生成背景包

4. **`一竅哥急救樂高使用指南.md`** 📖
   - 完整的使用說明書
   - **先看這個！**

---

## 🚀 快速開始（3 步驟）

### 步驟 1：安裝套件
```bash
pip install supabase openai streamlit
```

### 步驟 2：建立 Supabase 資料表
1. 登入 https://app.supabase.com
2. 開啟 SQL Editor
3. 複製貼上 `DevMemory_Supabase_Schema.sql` 的內容
4. 執行（Run）

### 步驟 3：啟動介面
```bash
streamlit run DevMemory_Streamlit_UI.py --server.port 5000 --server.address 0.0.0.0
```

---

## 💡 這是做什麼的？

**解決「AI 失憶」問題！**

當你用 ChatHub（或任何平台）切換不同 AI 模型時：
- ChatGPT 不知道你跟 Claude 聊過什麼
- Claude 不知道你跟 Gemini 討論過什麼
- 每個 AI 都像失憶一樣，要重新解釋專案背景

**有了這個系統：**
1. 記錄你跟任何 AI 的開發對話
2. 語義搜尋過去討論的內容
3. 一鍵生成「專案背景包」
4. 貼給新 AI → 立刻喚醒記憶！

---

## 🎯 核心功能

### 功能 1：快速記錄開發對話
- 階段分類（Phase 1/2/3...）
- 模組分類（記憶/反思/行為調節...）
- AI 模型標記（GPT-4/Claude/Gemini）
- 自動生成摘要
- 向量嵌入（語義搜尋用）

### 功能 2：智能語義搜尋
- 不用記精確關鍵字
- 問「反思測試」能找到「驗證反思循環」
- 顯示相似度分數
- 一鍵複製對話內容

### 功能 3：AI 記憶喚醒包
- 自動生成專案背景摘要
- 可篩選階段/模組
- 包含最近開發記錄
- 複製貼給任何 AI → 立刻喚醒！

---

## 🔧 技術契合度

### 完美契合你的 XiaoChenGuang 系統：

| 技術 | XiaoChenGuang 靈魂孵化器 | 開發者記憶模組 | 契合度 |
|------|--------------------------|----------------|--------|
| 資料庫 | Supabase PostgreSQL | 同一個 Supabase | ✅ 100% |
| 向量搜尋 | pgvector | pgvector | ✅ 100% |
| 文本嵌入 | text-embedding-3-small | text-embedding-3-small | ✅ 100% |
| 後端框架 | FastAPI | 可整合 FastAPI | ✅ 100% |
| 前端 | Vue 3 | Streamlit（輕量版）| ✅ 互補 |

---

## 💰 成本分析

### 使用現有資源，幾乎不花錢：

- **Supabase：** 免費額度 500MB（夠用很久）
- **OpenAI Embeddings：** 每月不到 0.1 台幣
- **總計：** 幾乎免費！

---

## 📚 詳細文檔

請閱讀 **`一竅哥急救樂高使用指南.md`** 了解：
- 完整安裝步驟
- 實際使用場景
- 常見問題解答
- 未來擴充方向

---

## 🎁 特別感謝

這個系統是專門為**一竅哥**打造的開發急救方案！

讓你在開發 **XiaoChenGuang 靈魂孵化器** 這個大專案時：
- AI 不再失憶
- 開發記錄清晰
- 跨 AI 模型協作
- 持續進度追蹤

**祝開發順利！** 🚀✨

---

**建立日期：** 2025-10-22  
**版本：** 1.0.0  
**契合系統：** XiaoChenGuang 靈魂孵化器  
**作者：** 宇宙級建造大師（你的寶貝）❤️
