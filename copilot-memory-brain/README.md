# Copilot 外掛記憶腦專案

## 專案概述

這是一個為 VS Code Copilot 提供外掛記憶功能的系統，讓 Copilot 能夠：
- 從小宸光的記憶系統讀取上下文、任務歷史與人格語氣
- 每次互動自動生成反思摘要並寫回共用資料庫
- 與小宸光共用記憶層，能彼此學習

## 架構

```
[前端 Ask Copilot 按鈕]
        ↓
[Copilot Memory Brain FastAPI - Port 8001]
        ↓
[共用記憶模組]
        ├ xiaochenguang_memories（主記憶）
        ├ xiaochenguang_reflections（反思摘要）
        └ xiaochenguang_personality（人格）
```

## 專案結構

```
copilot-memory-brain/
├── backend/
│   ├── main.py                    # FastAPI 主程式 (Port 8001)
│   ├── config.py                  # 配置管理
│   ├── routers/
│   │   ├── copilot_router.py      # Copilot 互動路由
│   │   ├── memory_router.py       # 記憶查詢路由
│   │   └── reflection_router.py   # 反思處理路由
│   └── modules/
│       └── copilot_memory.py      # Copilot 記憶整合邏輯
├── docs/
│   └── API.md                     # API 文檔
└── README.md
```

## 部署資訊

- **開發環境**: Replit
- **生產環境**: Railway
- **後端端口**: 8001
- **前端整合**: 整合到主 Vue 專案

## 資料庫共用

與小宸光系統共用 Supabase 資料庫：
- Redis: 共用實例（session 管理）
- Supabase: 共用表（通過 platform 標記區分）

## API 端點

- `POST /api/ask_copilot` - 發送問題給 Copilot
- `GET /api/memory/recent` - 取得最近記憶
- `GET /api/reflection/latest` - 取得最新反思
- `GET /health` - 健康檢查

## 版本

- **Version**: v2.0 (共用記憶版本)
- **Author**: 發財哥 × 小宸光
- **Date**: 2025-11-02
