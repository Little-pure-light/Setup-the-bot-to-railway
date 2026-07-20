# 回滾流程

## 何時回滾

- 正式環境聊天失敗率上升
- 部署後 `/ready` 長期 not_ready
- 嚴重資料寫入異常
- 安全事故

## 程式回滾（無 DB migration）

1. 確認目前錯誤版本（Railway Deployments / Git SHA）
2. 找到上一個穩定 Tag（如 `v1.0.1`）
3. Railway 重新部署該 Commit / Tag
4. `curl $BASE/live` 與 `$BASE/ready`
5. Smoke：發送一則測試訊息
6. 記錄事故原因

```bash
git log --oneline -20
git checkout v1.0.1
# 於 Railway 選該 SHA 部署
```

## 含資料庫 Migration

1. **先**確認是否有 Down migration
2. 若無：從備份還原 DB（`docs/RESTORE.md`）再回滾程式
3. 切勿只回滾程式而留下不相容 schema

## 前端

- Cloudflare Pages / 靜態託管：指回上一 production deploy
- 確認 `VITE_API_URL` 仍指向可用後端

## Smoke Test（回滾後）

- [ ] `/live` = ok
- [ ] `/ready` = ok 或可接受 degraded
- [ ] 登入（若使用）
- [ ] 發送「你好」有回覆
- [ ] 記憶未明顯錯亂

## Agent 限制

Agent 不得 force push、不得刪除 remote 歷史、不得自行合 main。
