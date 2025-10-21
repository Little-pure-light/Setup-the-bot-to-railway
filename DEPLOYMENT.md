# 部署指南

## 部署配置

此應用程式已配置為使用 Replit 的 Autoscale 部署模式，適合無狀態的 Web 應用。

### 部署設定摘要

- **部署目標**：Autoscale（自動擴展）
- **Web 伺服器**：Gunicorn（生產級 WSGI 伺服器）
- **綁定位址**：0.0.0.0:5000
- **Workers**：2 個工作進程
- **超時**：120 秒

### 必要的環境變數（Secrets）

在部署前，請確保已在 Replit 的部署設定中添加以下 secrets：

1. **SERVICE_ACCOUNT_JSON**（必填）
   - Google Sheets 服務帳號的 JSON 金鑰
   - 格式：完整的 JSON 字串
   - 範例：`{"type":"service_account","project_id":"...","private_key":"..."}`

2. **SPREADSHEET_ID**（必填）
   - Google Spreadsheet 的 ID
   - 從 Google Sheets 網址中取得
   - 範例：`1abc123xyz456...`

3. **SESSION_SECRET**（必填）
   - Flask session 加密金鑰
   - 使用隨機字串，建議至少 32 個字元
   - 範例：可用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成

### 部署步驟

1. **設定 Secrets**
   - 前往 Replit 專案的 Tools → Secrets
   - 添加上述三個 secrets

2. **點擊 Deploy 按鈕**
   - 在 Replit 介面中點擊「Deploy」
   - 選擇「Autoscale」部署模式
   - 確認 secrets 已正確配置

3. **等待部署完成**
   - 部署過程約需 2-5 分鐘
   - 系統會自動：
     - 安裝 Gunicorn
     - 啟動應用程式
     - 執行健康檢查

4. **驗證部署**
   - 訪問部署網址的 `/health` 端點
   - 應該看到：`{"status": "healthy", "service": "semantic-memory-system"}`
   - 訪問首頁 `/` 確認應用正常運行

### 健康檢查端點

應用程式提供了專用的健康檢查端點：

```
GET /health
```

回應範例：
```json
{
  "status": "healthy",
  "service": "semantic-memory-system"
}
```

此端點用於：
- Replit 部署的健康檢查
- 監控系統檢查應用狀態
- 快速驗證應用是否在線

### 部署配置檔案

部署配置已自動生成在 `.replit` 檔案中：

```toml
[deployment]
deploymentTarget = "cloudrun"
run = ["gunicorn", "--bind=0.0.0.0:5000", "--reuse-port", "--workers=2", "--timeout=120", "app:app"]
build = ["pip", "install", "gunicorn"]
```

### 常見部署問題

#### 1. 健康檢查失敗

**原因**：
- Secrets 未設定或設定錯誤
- 應用程式未綁定到 0.0.0.0:5000
- 啟動時間過長

**解決方法**：
- 確認所有 secrets 已正確添加
- 檢查部署日誌中的錯誤訊息
- `/health` 端點設計為快速響應，不依賴外部服務

#### 2. Google Sheets API 認證失敗

**原因**：
- `SERVICE_ACCOUNT_JSON` 格式錯誤
- 服務帳號權限不足
- Spreadsheet 未與服務帳號共用

**解決方法**：
- 確認 JSON 格式正確（完整的 JSON，不要截斷）
- 確認 Google Sheets 已與服務帳號共用（編輯權限）
- 確認已啟用 Google Sheets API 和 Drive API

#### 3. Session 問題

**原因**：
- `SESSION_SECRET` 未設定

**解決方法**：
- 添加 `SESSION_SECRET` 到部署 secrets
- 使用強隨機字串（至少 32 字元）

### 擴展配置

如需調整部署配置，可修改以下參數：

- **Workers 數量**：調整 `--workers=2` 參數
  - 建議：CPU 核心數 × 2 + 1
  - 範例：`--workers=4`

- **超時時間**：調整 `--timeout=120` 參數
  - 預設 120 秒
  - 如有長時間運行的請求，可增加此值

- **連接埠**：預設 5000
  - Replit 會自動處理外部端口映射
  - 無需修改

### 生產環境最佳實踐

1. ✅ 使用 Gunicorn 取代 Flask 開發伺服器
2. ✅ 設定適當的 worker 數量和超時時間
3. ✅ 使用強隨機的 SESSION_SECRET
4. ✅ 定期輪換 Google 服務帳號金鑰
5. ✅ 監控應用程式健康狀態（使用 /health 端點）
6. ✅ 啟用 HTTPS（Replit 自動提供）

### 監控與維護

- **健康檢查**：定期訪問 `/health` 端點
- **日誌檢查**：在 Replit 部署介面查看應用日誌
- **錯誤追蹤**：檢查 Google Sheets 操作的錯誤回應
- **效能監控**：觀察回應時間和 worker 使用情況

---

如有部署問題，請：
1. 檢查部署日誌
2. 驗證所有 secrets 已正確設定
3. 測試 `/health` 端點
4. 參考 SETUP_GUIDE.md 中的常見問題
