# 🚀 小宸光 AI 靈魂系統 - 部署指南

## ✅ 部署配置已完成

你的系統已經配置好生產環境部署！所有設定已自動完成。

## 📋 部署前檢查清單

### 必要的環境變數（Secrets）

確保以下 API 金鑰已設置：

- ✅ `OPENAI_API_KEY` - OpenAI API（GPT-4o-mini + Vision API）
- ✅ `SUPABASE_URL` - Supabase 資料庫連接
- ✅ `SUPABASE_KEY` - Supabase API 金鑰
- ✅ `REDIS_URL` - Redis 快取服務（Upstash）
- ✅ `PINATA_JWT` - Pinata IPFS 服務（對話封存）
- ✅ `PINECONE_API_KEY` - Pinecone 向量資料庫
- ✅ `PINECONE_ENVIRONMENT` - Pinecone 環境
- ✅ `PINECONE_INDEX_NAME` - Pinecone 索引名稱

### 資料庫表格

確保 Supabase 已建立以下表格：

1. `xiaochenguang_memories` - 對話記憶
2. `xiaochenguang_emotional_states` - 情緒狀態
3. `xiaochenguang_user_preferences` - 用戶偏好
4. `xiaochenguang_reflections` - AI 反思記錄
5. `conversation_archive` - IPFS 封存記錄

## 🎯 部署步驟

### 方法一：Replit 一鍵部署（推薦）

1. **點擊右上角的 "Deploy" 按鈕**
2. **選擇部署類型**：Autoscale（無狀態，自動擴展）
3. **確認設定**：
   - Build 命令：自動構建前端（`cd frontend && npm install && npm run build`）
   - Run 命令：生產級 Uvicorn 服務器
4. **點擊 "Deploy"**
5. **等待構建完成**（約 2-3 分鐘）
6. **獲得正式網址**：`https://your-app.replit.app`

### 方法二：手動部署檢查

如果需要手動檢查：

```bash
# 1. 構建前端
cd frontend
npm install
npm run build
cd ..

# 2. 測試生產服務器
uvicorn main:app --host 0.0.0.0 --port 5000

# 3. 訪問 http://localhost:5000 確認運行
```

## 🌐 部署架構

### 後端（FastAPI + Uvicorn）

- **框架**：FastAPI 3.0
- **服務器**：Uvicorn（ASGI 生產服務器）
- **端口**：5000（自動從 `PORT` 環境變數讀取）
- **靜態文件**：自動服務前端 `/frontend/dist`

### 前端（Vue 3 + Vite）

- **框架**：Vue 3 Composition API
- **構建工具**：Vite 5
- **輸出目錄**：`/frontend/dist`
- **路由**：Vue Router（History 模式）

### 資料層

- **長期記憶**：Supabase PostgreSQL（pgvector）
- **短期快取**：Redis（Upstash，2 天 TTL）
- **向量搜尋**：Pinecone（反思相似度搜尋）
- **檔案儲存**：Supabase Storage（永久）
- **對話封存**：IPFS（Pinata，永久保存）

## 🔒 安全性

### 已配置的安全措施

1. **CORS 保護**：僅允許特定域名
   - `https://ai.dreamground.net`
   - `https://ai2.dreamground.net`
   - `*.pages.dev`（Cloudflare Pages）
   - `*.replit.dev`（Replit 域名）

2. **環境變數隔離**：所有 API 金鑰通過環境變數管理

3. **SSL/TLS**：Redis 自動轉換為 `rediss://` 協議

4. **日誌安全**：不記錄敏感資訊

## 📊 監控建議

部署後建議監控：

1. **健康端點**：
   - `GET /health` - 基本健康檢查
   - `GET /api/health` - API 健康檢查

2. **日誌重點**：
   - Redis 連接狀態
   - Pinata IPFS 上傳成功率
   - OpenAI API 回應時間
   - Supabase 查詢效能

3. **關鍵指標**：
   - 對話回應時間（< 3 秒）
   - 記憶儲存成功率（> 95%）
   - 檔案上傳成功率（> 98%）
   - IPFS 封存成功率（> 90%）

## 🎨 自訂域名

如果要使用自訂域名（如 `ai.dreamground.net`）：

1. 在 Replit 部署設定中添加自訂域名
2. 在 DNS 服務商添加 CNAME 記錄指向 Replit
3. 等待 SSL 證書自動配置（約 5-10 分鐘）

## 🐛 常見問題

### 問題 1：前端構建失敗

**解決方案**：
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### 問題 2：Redis 連接失敗

**解決方案**：
- 確認 `REDIS_URL` 格式正確（支援 `redis://` 和 `rediss://`）
- 系統會自動轉換為 SSL 連接（Upstash）

### 問題 3：IPFS 上傳失敗

**解決方案**：
- 檢查 `PINATA_JWT` 是否正確
- 系統會自動降級到本地 CID 生成（不影響功能）

## 📞 支援

如有問題，請檢查：
1. Replit 部署日誌
2. `/health` 端點回應
3. 瀏覽器開發者工具控制台

---

**部署時間**：2025-11-01  
**版本**：v1.0.1 (Phase 3)  
**狀態**：✅ 生產就緒
