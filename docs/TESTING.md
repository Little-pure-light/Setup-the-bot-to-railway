# 測試執行說明（第一階段）

## 目標

- 不連線正式 OpenAI / Supabase / Redis / Railway
- 不使用正式 API Key
- 可在乾淨環境重複執行

## 安裝

在專案根目錄：

```bash
pip install -r requirements.txt
```

僅測試依賴也可：

```bash
pip install pytest pytest-asyncio pytest-cov httpx
```

## 執行後端測試

```bash
# 全部測試
pytest -q

# 僅單元測試
pytest -q -m unit

# 覆蓋率
pytest --cov=backend --cov=modules --cov-report=term-missing
```

Windows PowerShell 相同指令即可。

## 目錄結構

```text
tests/
├── conftest.py
├── unit/
│   ├── test_calculator.py
│   ├── test_unit_convert.py
│   ├── test_tool_registry.py
│   ├── test_emotion_detector.py
│   └── test_token_tracker.py
├── fixtures/
├── mocks/
│   ├── mock_openai.py
│   ├── mock_supabase.py
│   └── mock_redis.py
└── integration/   # 後續 P1-03 起
```

## 環境變數（測試用假值）

`tests/conftest.py` 會自動設定：

| 變數 | 測試值 |
|------|--------|
| `OPENAI_API_KEY` | `test-key-not-real` |
| `SUPABASE_URL` | `http://mock.supabase.local` |
| `SUPABASE_ANON_KEY` | `test-anon-key` |

正式 Secrets 請勿寫入測試檔。

## 與 Railway 的關係

- 測試套件不影響 `uvicorn main:app` 啟動流程
- `requirements.txt` 新增的 pytest 系列僅供開發/CI；生產可選擇不跑測試

## 後續（說明書 Sprint 1 剩餘）

- P1-03 API 整合測試
- P1-04 Streaming 測試
- P1-05 內建工具完整測試
- P1-06 記憶系統測試
