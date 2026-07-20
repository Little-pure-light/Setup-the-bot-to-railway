# 發版流程

## 版本號

`MAJOR.MINOR.PATCH`

| 類型 | 何時 |
|------|------|
| PATCH | Bug、安全小修、不改使用方式 |
| MINOR | 新功能、新工具、向後相容 |
| MAJOR | API 不相容、資料格式重大變更 |

## 發版步驟

1. 確認 `feature/*` 已 Review，CI 全綠
2. 更新 `CHANGELOG.md`（Unreleased → 版本段）
3. 合併至 `main`（由維護者操作，Agent 不自行合 main）
4. 打 Tag：

```bash
git checkout main
git pull
git tag -a v1.1.0 -m "v1.1.0"
git push origin v1.1.0
```

5. Railway 部署該 Commit / Tag
6. 驗證：

```bash
curl -s $BASE/live
curl -s $BASE/ready
# 前端 Smoke + 手動聊天
```

7. 記錄部署 SHA 到 CHANGELOG

## 發版檢查表

- [ ] CI 通過
- [ ] CHANGELOG 已寫
- [ ] 環境變數無變更或已文件化
- [ ] 無 DB migration 或 migration 已備妥
- [ ] `/live` `/ready` OK
- [ ] 電腦／手機基本聊天
- [ ] 回滾點（上一 Tag）明確

## 本文件範圍

只定義流程；**不**由 Agent 自行發正式 Release 或合併 main。
