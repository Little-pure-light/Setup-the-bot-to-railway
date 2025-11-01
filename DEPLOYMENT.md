# 🚀 小宸光 AI 靈魂系統 - 部署指南

## ✅ 部署配置已完成

你的系統採用**前後端分離架構**：
- **前端**：Vue 3 部署在 Cloudflare Pages ☁️
- **後端**：FastAPI 部署在 Replit（純 API 服務）🚀

## 🏗️ 系統架構

```
┌─────────────────────────────────────┐
│   Cloudflare Pages (前端)            │
│   https://ai.dreamground.net        │
│   - Vue 3 + Vite                    │
│   - 靜態資源 CDN 加速                 │
└─────────────┬───────────────────────┘
              │ API 請求
              ↓
┌─────────────────────────────────────┐
│   Replit (後端 API)                  │
│   https://your-app.replit.app       │
│   - FastAPI + Uvicorn               │
│   - 所有業務邏輯                      │
└─────────────┬───────────────────────┘
              │
     ┌────────┴────────┬─────────┬─────────┐
     ↓                 ↓         ↓         ↓
┌─────────┐    ┌──────────┐  ┌────────┐  ┌──────┐
│ Supabase│    │  Redis   │  │Pinecone│  │Pinata│
│PostgreSQL│   │ (Upstash)│  │ Vector │  │ IPFS │
└─────────┘    └──────────┘  └────────┘  └──────┘
```

## 📋 部署前檢查清單

### 必要的環境變數（Replit Secrets）

確保以下 API 金鑰已設置：

- ✅ `OPENAI_API_KEY` - OpenAI API（GPT-4o-mini + Vision API）
- ✅ `SUPABASE_URL` - Supabase 資料庫連接
- ✅ `SUPABASE_KEY` - Supabase API 金鑰
- ✅ `REDIS_URL` - Redis 快取服務（Upstash，自動轉換 SSL）
- ✅ `PINATA_JWT` - Pinata IPFS 服務（對話封存）
- ✅ `PINECONE_API_KEY` - Pinecone 向量資料庫
- ✅ `PINECONE_ENVIRONMENT` - Pinecone 環境
- ✅ `PINECONE_INDEX_NAME` - Pinecone 索引名稱

### 資料庫表格（Supabase）

確保已建立以下表格：

1. `xiaochenguang_memories` - 對話記憶
2. `xiaochenguang_emotional_states` - 情緒狀態
3. `xiaochenguang_user_preferences` - 用戶偏好
4. `xiaochenguang_reflections` - AI 反思記錄
5. `conversation_archive` - IPFS 封存記錄

**快速建立**：執行 `supabase_conversation_archive_schema.sql`

## 🎯 後端部署步驟（Replit）

### 一鍵部署（推薦）

1. **點擊右上角的 "Deploy" 按鈕** 🚀
2. **選擇部署類型**：Autoscale（無狀態，自動擴展）
3. **確認設定**：
   - Build 命令：無（純 API，不需要構建）
   - Run 命令：`uvicorn main:app --host 0.0.0.0 --port 5000`
4. **點擊 "Deploy"**
5. **等待 30-60 秒**，完成！✨
6. **獲得後端 API 網址**：`https://your-app.replit.app`

### 手動測試（可選）

```bash
# 測試本地 API 服務器
uvicorn main:app --host 0.0.0.0 --port 5000

# 測試健康端點
curl http://localhost:5000/health
```

## 🌐 前端配置（Cloudflare Pages）

### 環境變數設定

在 Cloudflare Pages 設定中添加：

```bash
VITE_API_URL=https://your-app.replit.app
```

**重要**：替換為你的實際 Replit 部署網址！

### 構建設定

- **構建命令**：`npm run build`
- **構建輸出目錄**：`dist`
- **根目錄**：`frontend`

## 🔒 CORS 安全配置

後端已預設允許以下來源：

```python
allow_origins=[
    "https://ai.dreamground.net",      # 你的主域名
    "https://ai2.dreamground.net",     # 備用域名
    "https://*.pages.dev",             # Cloudflare Pages 預覽
    "https://*.replit.dev",            # Replit 開發環境
    "http://localhost:3000",           # 本地開發
    "http://localhost:5000"
]
```

如需添加新域名，編輯 `main.py` 中的 CORS 設定。

## 📊 API 端點列表

部署後可用的端點：

### 健康檢查
- `GET  /` - 基本信息
- `GET  /health` - 系統健康狀態
- `GET  /api/health` - API 健康檢查

### AI 對話
- `POST /api/chat` - 發送訊息給 AI

### 記憶系統
- `GET  /api/memories/{conversation_id}` - 獲取對話記憶
- `GET  /api/emotional-states/{user_id}` - 獲取情緒狀態

### 檔案上傳（7 種格式）
- `POST /api/upload_file` - 上傳檔案
  - 支援：`.txt`, `.md`, `.json`, `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`
  - Vision API 自動分析圖片內容

### 對話封存
- `POST /api/archive_conversation` - 封存對話到 IPFS
  - 自動打包訊息 + 附件
  - 上傳到 Pinata IPFS
  - 返回公開網址

## 🧪 部署後測試

### 1. 健康檢查

```bash
curl https://your-app.replit.app/health
```

預期回應：
```json
{
  "status": "healthy",
  "service": "小晨光 AI",
  "version": "1.0.1"
}
```

### 2. API 測試

```bash
curl -X POST https://your-app.replit.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "你好",
    "user_id": "test_user",
    "conversation_id": "test_conv"
  }'
```

### 3. 檔案上傳測試

```bash
curl -X POST https://your-app.replit.app/api/upload_file \
  -F "file=@test.txt" \
  -F "conversation_id=test_conv" \
  -F "user_id=test_user"
```

## 🔧 常見問題

### 問題 1：前端無法連接後端

**症狀**：Cloudflare Pages 前端顯示網路錯誤

**解決方案**：
1. 檢查 Cloudflare Pages 環境變數 `VITE_API_URL` 是否正確
2. 確認後端 CORS 設定包含你的前端域名
3. 重新構建前端（Cloudflare Pages 會自動觸發）

### 問題 2：Redis 連接失敗

**症狀**：日誌顯示 "Connection closed by server"

**解決方案**：
- 系統會自動轉換 `redis://` 為 `rediss://`（SSL）
- 確認 `REDIS_URL` 格式正確
- 檢查 Upstash Redis 是否正常運行

### 問題 3：IPFS 上傳失敗

**症狀**：封存對話時返回本地 CID

**解決方案**：
- 檢查 `PINATA_JWT` 是否正確
- 系統會自動降級到本地 CID（不影響功能）
- 查看日誌確認 Pinata API 錯誤訊息

### 問題 4：Vision API 分析失敗

**症狀**：上傳圖片後無法獲得分析結果

**解決方案**：
- 確認 `OPENAI_API_KEY` 有效
- 檢查圖片格式（僅支援 `.png`, `.jpg`, `.jpeg`）
- 確認圖片大小 < 20MB

## 📈 監控建議

### 關鍵指標

1. **API 回應時間**
   - 對話：< 3 秒
   - 檔案上傳：< 5 秒
   - IPFS 封存：< 10 秒

2. **成功率**
   - 記憶儲存：> 95%
   - 檔案上傳：> 98%
   - IPFS 封存：> 90%（含 Pinata fallback）

3. **資源使用**
   - Redis 連接：穩定
   - Supabase 查詢：< 500ms
   - OpenAI API：< 2 秒

### 日誌監控

檢查 Replit 日誌中的：
- ✅ "Redis 已連接（URL 模式）"
- ✅ "Pinata API 已配置"
- ✅ "所有 router 掛載完成"
- ⚠️ 任何 ERROR 級別日誌

## 🎨 自訂域名

### Replit 後端域名

1. 在 Replit 部署設定中添加自訂域名
2. 添加 DNS CNAME 記錄：
   ```
   api.dreamground.net → your-app.replit.app
   ```
3. 更新前端 `VITE_API_URL` 為新域名

### Cloudflare Pages 前端域名

已配置：
- 主域名：`https://ai.dreamground.net`
- 備用域名：`https://ai2.dreamground.net`

## 🚀 快速命令參考

```bash
# 本地開發（後端）
python main.py

# 本地開發（前端）
cd frontend && npm run dev

# 構建前端（在 Cloudflare Pages 自動執行）
cd frontend && npm run build

# 測試健康檢查
curl https://your-app.replit.app/health

# 查看 Replit 日誌
# 在 Replit 控制台 → Logs 標籤
```

## 📞 技術支援

如有問題，按以下順序檢查：

1. **Replit 日誌**：查看錯誤訊息
2. **健康端點**：`/health` 確認服務狀態
3. **瀏覽器控制台**：檢查前端錯誤
4. **Supabase 儀表板**：確認資料庫連接
5. **Redis 狀態**：確認 Upstash 正常

---

**部署時間**：2025-11-01  
**版本**：v1.0.1 (Phase 3)  
**架構**：前後端分離（Cloudflare Pages + Replit）  
**狀態**：✅ 生產就緒
