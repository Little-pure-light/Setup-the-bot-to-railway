# 語義記憶管理系統

## 專案概述

這是一個基於 **Flask + Google Sheets** 的 AI 對話語義記憶管理系統，用於建立、延續、查詢及記錄 AI 對話內容。所有對話資料儲存於 Google Sheets 中，提供持久化、可查詢的記憶體系統。

## 專案狀態

✅ **已完成並可部署**（2025年10月21日）

## 最近更新

### 2025-10-21 晚間更新
- ✅ 完全重寫 app.py，修復所有 LSP 錯誤
- ✅ 改用環境變數取代 JSON 文件（更安全）
- ✅ 添加 /health 健康檢查端點（用於部署）
- ✅ 修復 gspread API 調用問題
- ✅ 創建 CSS 樣式文件（完整 UI）
- ✅ 配置生產級部署（Gunicorn + Autoscale）
- ✅ 撰寫超級簡單的人類友好設定指南
- ✅ 創建快速啟動指南（5分鐘版本）
- ✅ 全面測試並確保無錯誤

### 2025-10-21 早上
- ✅ 初始化 Flask 應用架構
- ✅ 實作所有核心 API 端點（/、/start、/log、/get_history、/summarize）
- ✅ 建立完整的 UI 介面（index、success、error 頁面）
- ✅ 新增完善的錯誤處理和輸入驗證
- ✅ 整合 Google Sheets API 認證
- ✅ 編寫詳細的設定指南和 README

## 核心功能

### 已實作功能

1. **首頁（GET /）**
   - 顯示當前使用中的對話記錄本
   - 提供「建立新對話」和「延續已有對話」選項
   - 簡潔清晰的 UI 介面

2. **啟動對話 API（GET /start）**
   - `mode=new`：建立新的 Google Sheets 工作表
   - `mode=resume`：載入現有工作表
   - 自動管理 session 狀態

3. **記錄對話 API（POST /log）**
   - 接收 user_message 和 ai_response
   - 自動加上時間戳記
   - 寫入當前啟用的工作表

4. **查詢歷史 API（GET /get_history）**
   - 回傳指定工作表的最近 N 筆對話
   - JSON 格式回應
   - 支援自訂 limit 參數

5. **摘要功能（POST /summarize）**
   - 預留端點，可整合 GPT/Claude API
   - 檢測對話數量（>50 筆觸發）
   - 未來可擴充至 IPFS 儲存

6. **錯誤處理**
   - 完整的錯誤處理機制
   - 友善的 HTML 錯誤頁面
   - JSON API 錯誤回應

### 預留擴充方向

- [ ] 實作摘要功能（整合 OpenAI/Claude API）
- [ ] IPFS 分散式儲存整合
- [ ] 對話搜尋功能
- [ ] 統計儀表板
- [ ] 匯出功能（JSON/CSV/Markdown）

## 技術架構

### 後端技術棧

- **Python 3.11**
- **Flask 3.1.2** - Web 框架
- **gspread 6.2.1** - Google Sheets Python API
- **google-auth 2.41.1** - Google API 認證
- **python-dotenv 1.1.1** - 環境變數管理

### 前端技術棧

- **Jinja2** - HTML 模板引擎
- **純 CSS** - 自訂樣式（漸層背景、卡片式設計）
- **Vanilla JavaScript** - 表單互動

### 資料儲存

- **Google Sheets** - 主要資料儲存
  - 每個對話一個工作表
  - 欄位：時間戳記、使用者訊息、AI 回應

## 專案結構

```
.
├── app.py                  # Flask 主應用程式（✅ 已修復所有 bug）
├── templates/              # Jinja2 HTML 模板
│   ├── index.html         # 首頁
│   ├── success.html       # 成功頁面
│   └── error.html         # 錯誤頁面
├── static/                # 靜態資源
│   └── style.css          # 樣式表（✅ 已創建）
├── README.md              # 專案說明
├── SETUP_GUIDE.md         # 詳細設定指南
├── DEPLOYMENT.md          # 部署指南
├── 設定指南.md             # 超簡單人類版設定指南 ⭐
├── 快速啟動.md             # 5分鐘快速啟動指南 ⭐
└── replit.md              # 本文件
```

## 環境變數設定

需要設定以下環境變數（請參閱 SETUP_GUIDE.md）：

```env
SERVICE_ACCOUNT_JSON={"type":"service_account",...}
SPREADSHEET_ID=your_spreadsheet_id
SESSION_SECRET=your_random_secret_key
```

## 使用者偏好設定

- 使用 **Python + Flask** 而非 JavaScript（明確需求）
- 偏好 **Google Sheets** 作為儲存方案
- 需要 **完整的中文註解**
- 強調 **友善的錯誤處理**
- UI 設計要求**簡潔清晰**
- **必須交付可立即使用的專案**（無技術漏洞）
- **設定文檔必須用地球語**（非技術人員也能看懂）

## 開發注意事項

### 已解決的問題

#### 晚間重大修復（2025-10-21）
1. ✅ **修復 Credentials API 錯誤**：完全重寫認證邏輯，改用環境變數
2. ✅ **修復 gspread API 調用**：使用正確的 `values` 和 `range_name` 參數
3. ✅ **修復所有 LSP 錯誤**：exception handler 變數綁定、類型檢查
4. ✅ **創建缺失的 CSS 文件**：完整的 UI 樣式表
5. ✅ **刪除不安全的文件依賴**：移除 sheel.json，全面使用環境變數

#### 早上修復
1. ✅ LSP 錯誤修復：exception handler 中的變數綁定問題
2. ✅ JSON 驗證：`/log` API 現在會檢查 JSON body 的有效性
3. ✅ 參數驗證：`/get_history` API 現在會驗證 limit 參數格式

### 安全性考量

- ✅ 使用環境變數管理敏感資訊
- ✅ .env 檔案已加入 .gitignore
- ✅ Session secret 使用環境變數
- ✅ 服務帳號認證遵循最佳實踐

### 已知限制

- 需要手動設定 Google Sheets API 認證
- `/log` API 依賴 session，需要先啟動對話
- 目前未實作使用者認證機制

## API 快速參考

### GET /
顯示首頁，提供建立/延續對話介面

### GET /start
啟動對話模式
- 參數：`mode` (new/resume), `sheet_name`

### POST /log
記錄對話內容
- Body: `{"user_message": "...", "ai_response": "..."}`

### GET /get_history
查詢歷史記錄
- 參數：`sheet_name`, `limit` (可選，預設5)

### POST /summarize
摘要功能（預留）
- 參數：`sheet_name`

## 開發環境

- **Replit** 環境
- **Python 3.11** 模組
- **Flask 開發伺服器**（port 5000）
- **Google Sheets API** 整合

## 部署建議

生產環境建議：
1. 使用 Gunicorn 或 uWSGI 取代 Flask 開發伺服器
2. 啟用 HTTPS
3. 加入 API 認證機制
4. 設定 rate limiting
5. 使用強隨機 SESSION_SECRET
6. 定期輪換服務帳號金鑰

## 參考文件

- [README.md](README.md) - 專案簡介和基本使用
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - 詳細設定指南（含 Google Sheets API 設定）
- [.env.example](.env.example) - 環境變數範例

## 聯絡與支援

如遇問題，請檢查：
1. SETUP_GUIDE.md 中的常見問題章節
2. Flask 伺服器日誌
3. Google Sheets 共用設定
4. 環境變數配置

---

**專案建立日期**：2025年10月21日  
**最後更新**：2025年10月21日  
**版本**：1.0.0
