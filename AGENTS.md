# Agent 開發規範（小宸光 AI）

適用於所有 AI Agent / 自動化修改本 repo 的行為。

## 修改前

1. 閱讀 `README.md`、`docs/PHASE1_PROGRESS.md`、相關模組
2. 確認分支：禁止直接改 `main`；使用 `feature/*` 或 `fix/*`
3. 說明現有流程與預計修改檔案
4. 列出風險（Streaming / Tool / 記憶 / 人格 / 語音 / 車載）
5. 不得一開始就大規模重構

## 核心高風險檔案

```text
backend/chat_router.py
backend/openai_handler.py
backend/prompt_engine.py
backend/tools/registry.py
modules/memory_system.py
modules/soul.py
frontend/src/components/ChatInterface.vue
```

修改時必須：說明原因、差異、測試、影響、回滾方式。

## 修改中

- 小範圍、向後相容
- 不改無關檔案、不整庫 reformat
- 不改環境變數名稱、不改既有 API 路徑
- 不刪除 Streaming / Tool Calling / 記憶 / 人格 / 語音
- 不把 Secret 寫進程式或測試
- 不連正式 OpenAI / Supabase 做測試
- 不用假結果冒充測試通過

## 修改後交付

```text
1. 修改摘要
2. 檔案清單
3. 新增依賴
4. 測試指令與結果
5. 已知限制
6. 風險
7. 回滾方式
```

## 測試要求

- 後端：`pytest -q`
- 前端：`cd frontend && npm run test && npm run build`
- 涉及 UI 流程：`npm run test:e2e`（Mock API）
- PR 必須通過 CI（見 `.github/workflows/ci.yml`）

## Secret 規範

禁止記錄或提交：

- OpenAI / Supabase keys
- JWT、密碼、完整 Authorization
- 真實使用者對話全文

日誌請用 `backend.logging_utils` 脫敏與短 ID。

## 驗收面向

- [ ] 電腦版
- [ ] 手機版
- [ ] 車載模式（若影響語音）
- [ ] 重新整理後可用
- [ ] Railway `/live` `/ready`

## 回滾

見 `docs/ROLLBACK.md`：切回上一 Tag / Commit，必要時還原 DB。
