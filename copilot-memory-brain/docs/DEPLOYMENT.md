# Copilot Memory Brain - Deployment Guide

## 部署架構

### 開發環境（Replit）
- **小宸光 AI 後端**: Port 5000
- **Copilot Memory Brain 後端**: Port 8080
- **前端**: 整合在小宸光 Vue 專案

### 生產環境（Railway）
- **後端部署**: 兩個獨立服務
  - Service 1: 小宸光 AI（預設端口）
  - Service 2: Copilot Memory Brain（Port 8080）
- **前端部署**: Cloudflare Pages
  - 環境變數:
    - `VITE_API_URL`: 小宸光 API URL
    - `VITE_COPILOT_API_URL`: Copilot API URL

## 環境變數配置

### Copilot Memory Brain 必要環境變數

```bash
# Redis（與小宸光共用）
REDIS_URL=...
REDIS_ENDPOINT=...
REDIS_TOKEN=...

# Supabase（與小宸光共用）
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_MEMORIES_TABLE=xiaochenguang_memories

# OpenAI
OPENAI_API_KEY=...
OPENAI_ORG_ID=...
OPENAI_PROJECT_ID=...
```

## Railway 部署步驟

### 1. 部署 Copilot Memory Brain

```bash
# 在 Railway 創建新 Service
# 設定 Start Command:
cd copilot-memory-brain/backend && python main.py

# 設定環境變數（從上方複製）
```

### 2. 更新前端環境變數（Cloudflare Pages）

```bash
# Production Environment Variables
VITE_API_URL=https://your-xiaochenguang-service.railway.app
VITE_COPILOT_API_URL=https://your-copilot-service.railway.app
```

### 3. 驗證部署

```bash
# 測試小宸光 API
curl https://your-xiaochenguang-service.railway.app/health

# 測試 Copilot API
curl https://your-copilot-service.railway.app/health

# 測試 Copilot 功能
curl -X POST https://your-copilot-service.railway.app/api/ask_copilot \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "測試問題",
    "conversation_id": "test_123",
    "user_id": "test_user"
  }'
```

## 故障排除

### Import Error
如果遇到 `ModuleNotFoundError`，確認：
1. PYTHONPATH 包含專案根目錄
2. 所有 __init__.py 檔案存在
3. sys.path 設定正確

### CORS Error
確認 main.py 的 CORS 配置包含您的前端域名

### Port Conflict
確保兩個後端使用不同端口（5000 vs 8080）

## 注意事項

1. **共用資料庫**: 兩個系統共用 Supabase 和 Redis，通過 `platform` 和 `source` 欄位區分
2. **端口配置**: 開發和生產環境端口可能不同，使用環境變數管理
3. **錯誤監控**: 建議設置 Sentry 或類似服務監控兩個後端
