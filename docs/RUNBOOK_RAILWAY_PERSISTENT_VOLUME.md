# Runbook — Railway 持久卷掛載（修「重部署掉記憶／人格」）

> 這份是給**有 Railway 權限的人**（一竅哥或維運）照著做的純步驟。Gate 1（本 PR）**不掛卷、不改 production**；
> 這份 Runbook 供 **Gate 2** 使用。一次一個動作，做完一步再做下一步。

## 這是在解決什麼？
Railway 容器的磁碟是「暫時的」：每次重新部署，容器裡的 `data/` 會被清空。小宸光的**身份（identity charter）**與
**記憶關聯（memory graph）**目前存在 `data/`，所以「重新部署 → 忘記你是誰、記憶歸零」。
把一個**持久卷（Persistent Volume）**掛在 `data/` 這個位置，之後重部署資料就會留著。

前提（已符合）：服務目前是**單一 replica**（`backend/railway.json` 的 `numReplicas: 1`）。持久卷適用單 replica。

## 掛載目標路徑
- 容器內的 `data/` 根目錄。程式的預設資料路徑以**程式碼位置**錨定（與工作目錄無關），
  在 Railway 標準映像下解析為 **`/app/data`**。
- 若你不確定實際路徑：先做「步驟 0 驗證現況」，看 `/ready` 或啟動日誌印出的 `persistence root=...`，
  那就是要掛的確切路徑。

## 步驟 0 — 掛載前先驗證現況（確認會抓到假成功）
1. 打開瀏覽器，前往：`https://ai2.dreamground.net/ready`
2. 找到 `services.persistence` 欄位。**現在應該是 `"ephemeral"`**（代表還沒掛卷）。
   - 同時 `persistence.root` 會顯示實際的 data 根路徑（例如 `/app/data`）——**記下這個路徑**，步驟 2 要用。
3. （可選）看 Railway 服務的 Deploy Logs，啟動時會有一行：
   `🗄️ persistence root=/app/data mode=ephemeral writable=True is_mount=False`
   以及一行警告 `⚠️ persistence mode=ephemeral（非持久卷）...`。這代表偵測正常運作。

## 步驟 1 — 在 Railway 建立並掛載 Volume
1. 登入 Railway，進入本專案 → 選到**後端服務**（跑 FastAPI 的那個）。
2. 進入服務的 **Settings**（或 **Volumes** 分頁）。
3. 點 **Add Volume / New Volume**（建立持久卷）。
4. **Mount path** 填入步驟 0 記下的 data 根路徑：**`/app/data`**（若步驟 0 顯示不同，就填那個）。
5. 儲存。Railway 會要求重新部署（redeploy）以套用掛載。

> 注意：**Mount path 一定要是 data 根本身（`/app/data`）**，不要掛在它的父層（例如 `/app`）。
> 掛錯層級，偵測會保守地回報 `ephemeral`（寧可不假成功）。

## 步驟 2 — 要不要改環境變數？
- **理想情況：不用改任何 env。** 只要 Volume 掛在預設的 data 根（`/app/data`），
  identity / memory graph / night_growth / token ledger / reminders 全都已落在這個根之下，自動就位。
- **只有在你把 Volume 掛到「不是」預設 data 根**（例如掛到 `/data`）時，才需要設定下列環境變數，
  讓程式指向該卷。全部設成「你的 mount path 之下」的對應位置（以 mount path = `/data` 為例）：
  | 環境變數 | 值（範例：mount=/data） |
  |---|---|
  | `PERSISTENCE_DATA_ROOT` | `/data` |
  | `IDENTITY_STORE_DIR` | `/data/identity` |
  | `MEMORY_GRAPH_FILE` | `/data/memory_graph.json` |
  | `NIGHT_GROWTH_STORE_DIR` | `/data/night_growth` |
  | `TOKEN_LEDGER_PATH` | `/data/token_ledger.jsonl` |
  | `REMINDERS_FILE` | `/data/reminders.json` |
  | `TOKEN_USAGE_LOG` | `/data/token_usage.jsonl` |
  設完後再 redeploy。
- **建議**：掛在 `/app/data`，就完全不必碰 env，最單純。

## 步驟 3 — 掛載後驗證「有真的掛上」
1. 等 redeploy 完成，再開 `https://ai2.dreamground.net/ready`。
2. `services.persistence` 應該從 `"ephemeral"` 變成 **`"volume"`**。
   - `persistence.is_mount` 應為 `true`、`persistence.writable` 應為 `true`。
3. 若仍是 `ephemeral`：表示卷沒掛在對的路徑 → 回步驟 1 確認 Mount path，或用步驟 2 的 env 對齊。

## 步驟 4 — 真正的驗收：重部署後資料仍在（這才算修好）
> 只看 `/ready` 顯示 volume **還不夠**；必須證明資料能跨重部署存活。這步請 Codex 依實際證據判定。
1. 透過正常使用讓小宸光**寫入一筆身份/記憶**（例如告訴它一件關於你的事、或觸發一次記憶關聯）。
2. 在 Railway **主動 redeploy 一次**（不改任何東西，純重新部署）。
3. redeploy 後回來確認**剛剛那筆身份/記憶仍在**（小宸光仍記得）。
   - 這才是「掉記憶 bug 已修」的唯一有效證據。**不可用單元測試或本機檔案存在冒充。**

## 回滾（若出問題）
- 在 Railway 服務的 Volumes 設定**移除該 Volume**並 redeploy，即回到掛卷前現況（仍用暫時磁碟）。
- 掛載路徑錯誤**不會毀資料**：最壞情況只是資料仍落在暫時磁碟（等同現況）。

## 附註
- 未來若要多 replica / 多人版，持久卷（綁單一實例）不再適用，需改走「方案 B：Supabase 持久化」
  （需 schema migration，另需明確批准）。本輪只做方案 A。
