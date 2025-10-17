# 小宸光 AI 靈魂系統 - 測試指南

## 快速啟動服務

### 方法 1: 使用測試腳本 (推薦)

```bash
./test_system.sh
```

### 方法 2: 手動啟動

#### 啟動後端 (Port 8000)
```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000
```

#### 啟動前端 (Port 5000) - 在新終端
```bash
cd frontend && npm run dev -- --host 0.0.0.0 --port 5000
```

---

## API 端點測試

### 1. 測試聊天功能

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "你好,小宸光!",
    "user_id": "test_user_001",
    "conversation_id": "test_conv_001"
  }'
```

**預期回應**:
- `ai_response`: 小宸光的回覆
- `emotion`: 偵測到的情緒
- `emotion_intensity`: 情緒強度
- `personality_traits`: 人格特質

### 2. 測試記憶檢索

```bash
curl "http://localhost:8000/api/memories/test_conv_001?limit=10"
```

**預期回應**: 對話記憶列表 (包含 user_message, assistant_mes, importance_score 等)

### 3. 測試情緒狀態

```bash
curl "http://localhost:8000/api/emotional-states/test_user_001?limit=5"
```

**預期回應**: 用戶情緒歷史記錄

### 4. 測試檔案上傳

```bash
# 創建測試文件
echo "這是測試文件" > test.txt

# 上傳文件
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@test.txt" \
  -F "conversation_id=test_conv_001" \
  -F "user_id=test_user_001"
```

**預期回應**: 上傳成功訊息,包含檔案 URL

---

## 前端介面測試

### 訪問網頁介面

1. **開啟瀏覽器**: http://localhost:5000
2. **測試功能**:
   - 輸入訊息並發送
   - 查看右側記憶列表
   - 查看情緒狀態標籤
   - 點擊「上傳檔案」按鈕測試上傳

### 預期行為

- ✅ 訊息發送後即時顯示
- ✅ AI 回覆帶有情緒標籤 (例如: 😊 joy)
- ✅ 記憶列表自動更新
- ✅ 情緒狀態面板顯示最新情緒

---

## 整合測試流程

### 完整對話測試

1. **發送第一條訊息**:
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "我今天很開心!",
    "user_id": "test_user_001",
    "conversation_id": "test_conv_001"
  }'
```

2. **檢查情緒偵測**: 應回傳 `emotion: "joy"` 

3. **發送第二條訊息** (測試記憶):
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "還記得我剛才說什麼嗎?",
    "user_id": "test_user_001",
    "conversation_id": "test_conv_001"
  }'
```

4. **驗證記憶**: AI 應該能提及「開心」相關內容

5. **查看記憶列表**:
```bash
curl "http://localhost:8000/api/memories/test_conv_001"
```

---

## 檢查日誌

### 後端日誌
```bash
tail -f logs/backend.log
```

### 查看錯誤訊息
```bash
cat logs/backend.log | grep "ERROR\|❌"
```

---

## 常見問題排查

### 問題 1: 記憶功能出錯
**錯誤**: `column assistant_mes does not exist`

**解決方案**: 
1. 確認已按照 `DATABASE_SETUP.md` 建立資料表
2. 檢查 Supabase 資料表結構

### 問題 2: OpenAI API 錯誤
**錯誤**: `AuthenticationError` or `RateLimitError`

**解決方案**:
1. 檢查環境變數 `OPENAI_API_KEY` 是否正確
2. 確認 API 額度充足

### 問題 3: 前端無法連接後端
**錯誤**: `Network Error` 或 `CORS Error`

**解決方案**:
1. 確認後端運行在 port 8000
2. 檢查 `backend/main.py` 的 CORS 設定
3. 確認 `frontend/vite.config.js` 的 proxy 設定

---

## 停止服務

### 停止後端
```bash
# 找到進程 ID
ps aux | grep uvicorn

# 終止進程
kill <PID>
```

### 停止前端
```bash
# 找到進程 ID
ps aux | grep vite

# 終止進程
kill <PID>
```

### 或使用一鍵停止 (小心使用)
```bash
# 停止所有相關進程 (需要確保 PID 正確)
ps aux | grep -E "(uvicorn|vite)" | grep -v grep | awk '{print $2}' | xargs kill
```

---

## 效能測試

### 測試回應時間
```bash
time curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "測試效能",
    "user_id": "test_user_001",
    "conversation_id": "test_conv_001"
  }'
```

### 預期效能
- 記憶檢索: < 500ms
- AI 回應生成: 2-5 秒 (取決於 OpenAI API)
- 情緒分析: < 100ms

---

## 自動化測試

創建測試腳本 `run_tests.sh`:

```bash
#!/bin/bash

echo "🧪 測試聊天功能..."
curl -s -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "你好",
    "user_id": "test_user",
    "conversation_id": "test_conv"
  }' | jq '.ai_response'

echo ""
echo "🧪 測試記憶檢索..."
curl -s "http://localhost:8000/api/memories/test_conv?limit=5" | jq 'length'

echo ""
echo "🧪 測試情緒狀態..."
curl -s "http://localhost:8000/api/emotional-states/test_user?limit=5" | jq 'length'

echo ""
echo "✅ 測試完成!"
```

運行:
```bash
chmod +x run_tests.sh && ./run_tests.sh
```

---

## 生產環境準備

### 環境變數檢查
```bash
# 確認所有必要的環境變數
env | grep -E "(OPENAI|SUPABASE)"
```

必須有:
- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

### 資料庫檢查
```bash
# 測試 Supabase 連接
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"user_message": "test", "user_id": "test", "conversation_id": "test"}'
```

如果有資料庫錯誤,參考 `DATABASE_SETUP.md`

---

## 下一步

- ✅ 完成資料庫設置 (DATABASE_SETUP.md)
- ✅ 測試所有 API 端點
- ✅ 驗證前端功能
- ✅ 檢查錯誤日誌
- 🚀 準備部署上線
