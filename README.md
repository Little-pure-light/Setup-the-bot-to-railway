# 語義記憶管理系統

基於 Flask + Google Sheets 的 AI 對話延續與記憶應用系統。

## 功能特色

- ✅ **建立新對話**：在 Google Sheets 中建立新的對話記錄工作表
- ✅ **延續已有對話**：載入並繼續之前的對話記錄
- ✅ **記錄對話**：自動記錄時間戳記、使用者訊息、AI 回應
- ✅ **查詢歷史**：取得指定工作表的最近 N 筆對話記錄
- 🔜 **摘要功能**：預留 `/summarize` 端點，可整合 GPT/Claude API
- 🔜 **IPFS 整合**：未來可將摘要儲存至分散式儲存

## 系統架構

```
語義記憶管理系統
├── Flask Web 應用
├── Google Sheets（資料儲存）
│   └── 多個工作表（每個對話一個工作表）
└── Session 管理（追蹤當前使用的工作表）
```

## 安裝與設定

### 1. 安裝相依套件

```bash
pip install flask gspread google-auth python-dotenv
```

或使用 `uv`（Replit 環境）：

```bash
uv add flask gspread google-auth python-dotenv
```

### 2. Google Sheets API 設定

#### 步驟 A：建立 Google Cloud 專案

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立新專案或選擇現有專案
3. 啟用以下 API：
   - Google Sheets API
   - Google Drive API

#### 步驟 B：建立服務帳號

1. 在 Google Cloud Console，前往「IAM 與管理」→「服務帳號」
2. 建立服務帳號
3. 下載 JSON 金鑰檔案
4. 複製整個 JSON 內容

#### 步驟 C：建立 Google Spreadsheet

1. 前往 [Google Sheets](https://sheets.google.com/)
2. 建立新的試算表
3. 將試算表分享給服務帳號的電子郵件地址（編輯權限）
   - 服務帳號 email 格式：`xxx@xxx.iam.gserviceaccount.com`
4. 從網址列複製 Spreadsheet ID：
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
   ```

### 3. 環境變數設定

複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

編輯 `.env` 檔案並填入：

```env
SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...整個JSON內容..."}
SPREADSHEET_ID=你的_spreadsheet_id
SESSION_SECRET=請更換為隨機字串
```

**注意**：`SERVICE_ACCOUNT_JSON` 必須是完整的 JSON 字串（單行）。

### 4. 執行應用程式

```bash
python app.py
```

應用程式將在 `http://0.0.0.0:5000` 啟動。

## API 使用說明

### 1. 首頁（GET /）

顯示當前使用的對話記錄本，提供建立新對話或延續已有對話的介面。

### 2. 啟動對話（GET /start）

**參數：**
- `mode`: `new`（建立新對話）或 `resume`（延續已有對話）
- `sheet_name`: 工作表名稱

**範例：**

```bash
# 建立新對話
http://localhost:5000/start?mode=new&sheet_name=專案討論_2024

# 延續已有對話
http://localhost:5000/start?mode=resume&sheet_name=專案討論_2024
```

### 3. 記錄對話（POST /log）

**Content-Type:** `application/json`

**參數：**
```json
{
  "user_message": "你好，請問今天天氣如何？",
  "ai_response": "今天天氣晴朗，溫度約 25 度。"
}
```

**範例：**

```bash
curl -X POST http://localhost:5000/log \
  -H "Content-Type: application/json" \
  -b "session=YOUR_SESSION_COOKIE" \
  -d '{
    "user_message": "你好，請問今天天氣如何？",
    "ai_response": "今天天氣晴朗，溫度約 25 度。"
  }'
```

**回應：**

```json
{
  "status": "success",
  "message": "對話已成功記錄",
  "timestamp": "2024-10-21 14:30:45"
}
```

### 4. 查詢歷史記錄（GET /get_history）

**參數：**
- `sheet_name`: 工作表名稱（必填）
- `limit`: 返回最近幾筆記錄（預設 5）

**範例：**

```bash
curl "http://localhost:5000/get_history?sheet_name=專案討論_2024&limit=10"
```

**回應：**

```json
{
  "status": "success",
  "sheet_name": "專案討論_2024",
  "total_records": 25,
  "returned_records": 10,
  "history": [
    {
      "timestamp": "2024-10-21 14:30:45",
      "user_message": "你好，請問今天天氣如何？",
      "ai_response": "今天天氣晴朗，溫度約 25 度。"
    },
    ...
  ]
}
```

### 5. 摘要功能（POST /summarize）【預留】

當對話超過 50 筆時，可呼叫此 API 進行摘要（目前為預留功能）。

**參數：**
- `sheet_name`: 工作表名稱

**範例：**

```bash
curl -X POST "http://localhost:5000/summarize?sheet_name=專案討論_2024"
```

## 專案結構

```
.
├── app.py                  # Flask 主應用程式
├── templates/              # HTML 模板
│   ├── index.html         # 首頁
│   ├── success.html       # 成功頁面
│   └── error.html         # 錯誤頁面
├── static/                # 靜態資源
│   └── style.css          # 樣式表
├── .env.example           # 環境變數範例
├── .env                   # 環境變數（不納入版控）
└── README.md              # 本文件
```

## 錯誤處理

系統包含完整的錯誤處理機制：

- **工作表已存在**：建立新對話時，若名稱已存在會顯示錯誤
- **工作表不存在**：延續對話時，若名稱不存在會顯示錯誤
- **認證失敗**：Google Sheets API 認證問題會顯示明確錯誤訊息
- **缺少參數**：API 呼叫缺少必要參數會返回 400 錯誤

所有錯誤都會以友善的 HTML 頁面或 JSON 格式回應。

## 未來擴充方向

1. **摘要功能實作**
   - 整合 OpenAI GPT 或 Anthropic Claude API
   - 當對話超過 50 筆時自動產生摘要
   - 將摘要儲存至 Google Sheets 或 IPFS

2. **IPFS 整合**
   - 將長對話或摘要儲存至 IPFS 分散式儲存
   - 在 Google Sheets 中記錄 IPFS CID

3. **搜尋功能**
   - 支援關鍵字搜尋歷史對話
   - 時間範圍篩選

4. **統計儀表板**
   - 顯示各工作表的對話數量
   - 最後更新時間
   - 對話趨勢圖表

5. **匯出功能**
   - 支援匯出為 JSON、CSV、Markdown 格式

## 部署到生產環境

### 使用 Replit 部署

本應用已配置為使用 Replit Autoscale 部署模式，適合無狀態 Web 應用：

#### 部署步驟

1. **設定必要的 Secrets**（在 Replit 部署設定中）：
   - `SERVICE_ACCOUNT_JSON` - Google 服務帳號 JSON 金鑰
   - `SPREADSHEET_ID` - Google Spreadsheet ID
   - `SESSION_SECRET` - Flask session 加密金鑰（建議使用隨機 64 字元）

2. **點擊 Deploy 按鈕**：
   - 選擇「Autoscale」部署模式
   - 確認所有 secrets 已正確配置

3. **驗證部署**：
   - 訪問 `/health` 端點應該回傳 `{"status": "healthy"}`
   - 訪問首頁確認應用正常運行

#### 部署配置

- **Web 伺服器**：Gunicorn（生產級 WSGI 伺服器）
- **Workers**：2 個工作進程
- **超時**：120 秒
- **健康檢查端點**：`GET /health`
- **自動擴展**：根據流量自動調整資源

詳細部署說明請參閱 [DEPLOYMENT.md](DEPLOYMENT.md)

## 安全性注意事項

- ⚠️ **絕不要**將 `.env` 檔案提交到版本控制系統
- ⚠️ **絕不要**在程式碼中硬編碼 API 金鑰
- ⚠️ 在生產環境中，請將 `SESSION_SECRET` 更換為強隨機字串
- ⚠️ 定期輪換服務帳號金鑰
- ✅ 部署使用 HTTPS（Replit 自動提供）
- ✅ 生產環境使用 Gunicorn 而非 Flask 開發伺服器

## 授權

本專案為範例程式碼，供學習與研究使用。

## 聯絡方式

如有問題或建議，請開啟 Issue 或 Pull Request。
