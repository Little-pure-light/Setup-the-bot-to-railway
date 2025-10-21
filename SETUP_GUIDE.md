# 語義記憶管理系統 - 詳細設定指南

## 目錄

1. [快速開始](#快速開始)
2. [Google Sheets API 設定](#google-sheets-api-設定)
3. [環境變數配置](#環境變數配置)
4. [測試系統](#測試系統)
5. [常見問題](#常見問題)

---

## 快速開始

### 前置需求

- Python 3.11 或更高版本
- Google 帳號
- 基本的終端機/命令列使用經驗

### 安裝步驟

1. **安裝相依套件**

```bash
# 使用 pip
pip install flask gspread google-auth python-dotenv

# 或使用 uv（推薦）
uv add flask gspread google-auth python-dotenv
```

2. **配置環境變數**（詳見下方說明）

3. **執行應用程式**

```bash
python app.py
```

應用程式將在 `http://0.0.0.0:5000` 啟動。

---

## Google Sheets API 設定

### 步驟 1：建立 Google Cloud 專案

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 點擊頂部的「選取專案」→「新增專案」
3. 輸入專案名稱（例如：「語義記憶系統」）
4. 點擊「建立」

### 步驟 2：啟用必要的 API

1. 在 Google Cloud Console 中，確保已選取您剛建立的專案
2. 前往「API 和服務」→「資料庫」
3. 點擊「+ 啟用 API 和服務」
4. 搜尋並啟用以下 API：
   - **Google Sheets API**
   - **Google Drive API**

### 步驟 3：建立服務帳號

1. 前往「IAM 與管理」→「服務帳號」
2. 點擊「+ 建立服務帳號」
3. 填寫服務帳號資訊：
   - **服務帳號名稱**：例如「memory-system-service」
   - **服務帳號 ID**：自動產生
   - **描述**：選填
4. 點擊「建立並繼續」
5. 角色設定可以跳過（點擊「繼續」）
6. 點擊「完成」

### 步驟 4：建立服務帳號金鑰

1. 在服務帳號列表中，找到您剛建立的服務帳號
2. 點擊該服務帳號的電子郵件地址
3. 切換到「金鑰」分頁
4. 點擊「新增金鑰」→「建立新的金鑰」
5. 選擇「JSON」格式
6. 點擊「建立」
7. JSON 金鑰檔案將自動下載到您的電腦

⚠️ **重要**：請妥善保管此 JSON 檔案，不要分享給他人！

### 步驟 5：建立 Google Spreadsheet

1. 前往 [Google Sheets](https://sheets.google.com/)
2. 點擊「空白」建立新試算表
3. 為試算表命名（例如：「AI 對話記憶庫」）
4. **重要**：點擊右上角的「共用」按鈕
5. 在「新增使用者或群組」欄位中，貼上服務帳號的電子郵件地址
   - 格式類似：`xxx@xxx.iam.gserviceaccount.com`
   - 可以在服務帳號頁面或 JSON 金鑰檔案中找到
6. 將權限設為「編輯者」
7. **取消勾選**「通知使用者」（因為這是服務帳號，不是真人）
8. 點擊「共用」
9. 從瀏覽器網址列複製 Spreadsheet ID：
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
   ```
   中間的 `SPREADSHEET_ID` 就是您需要的 ID

---

## 環境變數配置

### 方法 1：使用 .env 檔案（推薦）

1. 在專案根目錄建立 `.env` 檔案：

```bash
touch .env
```

2. 開啟您下載的 JSON 金鑰檔案，複製**整個 JSON 內容**

3. 編輯 `.env` 檔案，填入以下內容：

```env
# 將整個 JSON 內容作為單行字串貼在這裡（保持為一行）
SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"your-project-id","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"xxx@xxx.iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}

# 從 Google Sheets 網址中複製的 ID
SPREADSHEET_ID=1abc123xyz456_YOUR_SPREADSHEET_ID_HERE

# Flask session 密鑰（請更換為隨機字串）
SESSION_SECRET=your-random-secret-key-here-please-change-this-to-something-secure
```

**重要提示**：
- `SERVICE_ACCOUNT_JSON` 必須是**單行**字串
- 不要在 JSON 內容前後加引號（除非是 JSON 本身的引號）
- 確保沒有換行符號

### 方法 2：使用環境變數（Replit 或部署環境）

如果您在 Replit 或其他雲端平台上運行：

1. 前往 Replit 的「Secrets」（Tools → Secrets）
2. 新增以下 secrets：
   - `SERVICE_ACCOUNT_JSON`：貼上完整的 JSON 內容
   - `SPREADSHEET_ID`：貼上您的 Spreadsheet ID
   - `SESSION_SECRET`：輸入一個隨機字串

### 產生安全的 SESSION_SECRET

使用 Python 產生隨機 secret：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

將輸出的字串設定為 `SESSION_SECRET`。

---

## 測試系統

### 1. 啟動應用程式

```bash
python app.py
```

您應該會看到：

```
 * Running on http://0.0.0.0:5000
```

### 2. 開啟瀏覽器

前往 `http://localhost:5000`

### 3. 建立新對話

1. 在「建立新對話」區塊輸入對話名稱，例如：`測試對話_2024`
2. 點擊「建立新對話」
3. 如果設定正確，您會看到成功訊息

### 4. 檢查 Google Sheets

1. 開啟您的 Google Spreadsheet
2. 您應該會看到新增了一個名為「測試對話_2024」的工作表
3. 該工作表應有三個欄位：時間戳記、使用者訊息、AI 回應

### 5. 測試記錄對話 API

使用 curl 或任何 HTTP 客戶端：

```bash
curl -X POST http://localhost:5000/log \
  -H "Content-Type: application/json" \
  -c cookies.txt -b cookies.txt \
  -d '{
    "user_message": "這是測試訊息",
    "ai_response": "這是 AI 的回應"
  }'
```

**注意**：需要先透過瀏覽器啟動對話以獲得 session cookie。

### 6. 測試查詢歷史 API

```bash
curl "http://localhost:5000/get_history?sheet_name=測試對話_2024&limit=5"
```

---

## 常見問題

### Q1: 遇到 "SERVICE_ACCOUNT_JSON 未設定" 錯誤

**解決方法**：
- 確認 `.env` 檔案存在於專案根目錄
- 檢查 `SERVICE_ACCOUNT_JSON` 是否正確設定
- 確保 JSON 內容是單行字串

### Q2: 遇到 "找不到工作表" 錯誤

**解決方法**：
- 確認您已在瀏覽器中先啟動對話（建立或延續）
- 檢查 Google Sheets 中是否真的存在該工作表
- 確認工作表名稱大小寫是否完全一致

### Q3: 遇到認證相關錯誤

**解決方法**：
- 確認已啟用 Google Sheets API 和 Google Drive API
- 確認 Google Sheets 已與服務帳號共用（編輯權限）
- 檢查 JSON 金鑰檔案是否完整且正確

### Q4: 無法寫入 Google Sheets

**解決方法**：
- 確認服務帳號有「編輯者」權限（不是「檢視者」）
- 檢查 Spreadsheet ID 是否正確
- 嘗試在 Google Sheets 介面手動新增一筆資料，確認試算表沒有被保護

### Q5: POST /log 回傳 "尚未啟動對話" 錯誤

**解決方法**：
- 使用 `/log` API 前，必須先透過 `/start` 端點啟動對話
- 或在瀏覽器中先建立/延續對話
- 確保使用相同的 session（使用 cookie）

### Q6: 如何在程式中使用這個系統？

**範例（Python）**：

```python
import requests

BASE_URL = "http://localhost:5000"

# 建立 session 以保持 cookie
session = requests.Session()

# 1. 啟動對話
response = session.get(f"{BASE_URL}/start", params={
    "mode": "new",
    "sheet_name": "我的對話_2024"
})
print(response.text)

# 2. 記錄對話
response = session.post(f"{BASE_URL}/log", json={
    "user_message": "你好",
    "ai_response": "你好！有什麼我可以幫助你的嗎？"
})
print(response.json())

# 3. 查詢歷史
response = session.get(f"{BASE_URL}/get_history", params={
    "sheet_name": "我的對話_2024",
    "limit": 5
})
print(response.json())
```

---

## 安全性建議

1. ✅ **絕不要**將 `.env` 檔案提交到 Git
2. ✅ **絕不要**在程式碼中硬編碼 API 金鑰
3. ✅ 定期輪換服務帳號金鑰
4. ✅ 在生產環境使用強隨機的 `SESSION_SECRET`
5. ✅ 限制服務帳號的權限範圍（只共用必要的 Spreadsheet）
6. ✅ 使用 HTTPS（在生產環境）
7. ✅ 考慮加入 API 認證機制（如 API key 或 OAuth）

---

## 下一步

系統已包含所有基本功能。您可以：

1. 整合到您的 AI 應用中
2. 實作摘要功能（`/summarize` 端點已預留）
3. 新增使用者認證
4. 部署到生產環境（使用 Gunicorn、uWSGI 等）
5. 擴充至 IPFS 儲存

---

## 需要協助？

如遇到問題，請檢查：

1. Flask 伺服器日誌（終端機輸出）
2. Google Sheets 共用設定
3. `.env` 檔案格式
4. 網路連線狀態

祝您使用愉快！ 🎉
