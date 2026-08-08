# Runbook — API_SECRET 輪替（Gate 2，一竅哥本人操作）

> 目的：把可能已外洩的 `API_SECRET` 換成全新值，並讓所有持有處同步。
> 鐵則：**新舊 secret 值一律由你本人輸入**；施工代理不經手任何值。本檔不含任何 secret 值。
> Gate 1（稽核＋硬化＋本 Runbook）已完成並經 Codex 複核；**真正輪替完成的唯一證據＝Gate 2 實測「舊值 401 / 新值 200」**。

## 先備知識：哪些地方持有 API_SECRET
1. **Railway** backend 服務的環境變數 `API_SECRET`。
2. **Open WebUI** → Admin → Connections → OpenAI → **API Key**（值＝`API_SECRET`）。
3. **隱性連動**：若 `NIGHT_GROWTH_INTERNAL_TOKEN` 沒有單獨設定，內部 night-growth 呼叫會**回退**使用 `API_SECRET`。本次建議**順便單獨設定** `NIGHT_GROWTH_INTERNAL_TOKEN`（與 `API_SECRET` 脫鉤），以後換其一不互相影響。
4. **舊自製前端（Cloudflare）**：已決定停用。它在**建置時**把 `VITE_API_SECRET` 烤進公開 JS bundle，所以舊版前端會**一直用舊值**打正式 API——輪替後它會自動失敗（401），這正是我們要的；請於本輪一併**下架該 Cloudflare 部署**，避免舊 bundle 繼續嘗試。

---

## 步驟（一次一步，做完再做下一步）

### 1. 產生新值（你本人操作）
- 產生一個**新的強隨機字串**當新 `API_SECRET`：純英數、夠長（建議 ≥ 32 字元）。
- （建議）再產生**另一個**不同的強隨機字串當 `NIGHT_GROWTH_INTERNAL_TOKEN`。
- 這兩個值請**自己保管**，不要貼進任何對話、issue、commit、截圖。

### 2. 更新 Railway backend 環境變數
- 進入 Railway → 你的 backend 服務 → **Variables**。
- 把 `API_SECRET` 的值**換成步驟 1 的新值**。
- （建議）**新增** `NIGHT_GROWTH_INTERNAL_TOKEN`＝步驟 1 的第二個新值。
- 先**不要**急著關掉頁面；記得 Railway 改變數通常會觸發重部署（見步驟 4）。

### 3. 更新 Open WebUI 的 API Key
- 進入 Open WebUI → **Admin → Connections → OpenAI → API Key**。
- 改成**與步驟 2 相同的新 `API_SECRET` 值**（兩邊必須一致，否則 Open WebUI 會打不通後端）。
- 儲存。

### 4. 觸發 backend 重部署
- 若 Railway 改變數後未自動重部署，手動 **Redeploy** 一次。
- 等部署完成、服務回到健康狀態（可看 `/health`、`/ready`）。

### 5. 驗證（這是 Gate 2 的驗收證據）
逐項確認（**不要把值貼進聊天**；只看狀態碼）：
- **舊值 → 401**：用**舊** `API_SECRET` 當 Bearer 打一個受保護端點（例如 `GET /v1/models` 或 `GET /api/tools`）→ 應得 **401**。
- **新值 → 200/非 401**：用**新** `API_SECRET` 當 Bearer 打同一端點 → 應**通過 auth**（非 401）。
- **Open WebUI 可聊天**：在 Open WebUI 實際送一則訊息 → 能正常收到回覆。
- （若有設 `NIGHT_GROWTH_INTERNAL_TOKEN`）內部 night-growth 端點用**新的內部 token** → 通過；用舊值 → 401。

### 6. 收尾
- 確認**舊值已全面失效**、沒有殘留客戶端仍用舊值（特別是舊 Cloudflare 前端已下架）。
- 把驗證結果（只記「舊值 401 / 新值 200 / Open WebUI 可聊天」等狀態，不含任何值）交 Codex 判定 Gate 2 完成。

---

## 疑難排解
- **Open WebUI 突然打不通**：多半是步驟 2 與步驟 3 的值**沒對齊**；回頭確認兩邊是同一新值。
- **內部 night-growth 壞掉**：若你這次才第一次單獨設 `NIGHT_GROWTH_INTERNAL_TOKEN`，記得呼叫端也要改用這個新 token；若暫時不想動它，可先不設（會回退用 `API_SECRET`，但就沒有脫鉤的好處）。
- **改完仍能用舊值**：可能重部署沒生效或改到別的服務／環境；確認改的是**正式 backend 服務**的 Variables 後再 Redeploy。

## 安全備註
- 後端程式**只從環境變數讀** `API_SECRET`，比對採**常數時間**（`hmac.compare_digest`），401 回應**不回顯**你送的 token；日誌有 secret 去敏。故只要平台端換值 + 舊客戶端下架，輪替即完成。
- 這份 Runbook 與相關報告**全程去敏**，不含任何 secret 值。
