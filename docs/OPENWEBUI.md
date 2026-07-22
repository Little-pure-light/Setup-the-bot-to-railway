# Open WebUI 連線設定（OpenAI 相容 API）

小宸光後端提供 OpenAI Chat Completions 相容介面，供 Open WebUI 使用。  
既有 `POST /api/chat` 與前端**不需變更**。

## 端點

| Method | Path | 說明 |
|--------|------|------|
| GET | `/v1/models` | 回傳模型 `xiaochenguang` |
| POST | `/v1/chat/completions` | 轉接既有聊天管線（記憶／人格／工具／串流／Kernel） |

## Railway 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `API_SECRET` | **強烈建議** | 保護 `/api/*` 與 `/v1/*`；Open WebUI 的 API Key 請填此值 |
| `OPENAI_API_KEY` | 是 | 既有 OpenAI 呼叫 |
| `SUPABASE_URL` / `SUPABASE_KEY` 或 `SUPABASE_ANON_KEY` | 是 | 記憶與同步 |
| 其餘 | 同既有部署 | 見 `ENVIRONMENT_VARIABLES.md` |

## Open WebUI 設定

1. **Admin → Connections → OpenAI**
2. **API Base URL**（重要：不要加 `/v1` 以外的路徑，Open WebUI 會自動接 `/v1/...`）：

   ```text
   https://<YOUR-RAILWAY-HOST>
   ```

   範例：`https://setup-the-bot-to-railway-production.up.railway.app`

   若介面要求「完整到 /v1」：

   ```text
   https://<YOUR-RAILWAY-HOST>/v1
   ```

   （依 Open WebUI 版本擇一；多數版本填 **origin 根網址** 即可。）

3. **API Key**：

   ```text
   <與 Railway 的 API_SECRET 相同的字串>
   ```

   Open WebUI 會以 `Authorization: Bearer <API Key>` 送出。

4. **Model**：選擇 / 應顯示 `xiaochenguang`。

## 對話 ID（記憶延續）

後端優先讀取 header：

- `X-Conversation-Id`
- `X-OpenWebUI-Chat-Id`
- `X-Chat-Id`
- `X-Session-Id`

或 body：`conversation_id` / `chat_id` / `session_id`。  
若皆無，則以 `user_id + default` 產生**穩定** id（同一使用者多輪不重開對話）。

## 驗證

```bash
# 模型列表
curl -s -H "Authorization: Bearer $API_SECRET" \
  https://<HOST>/v1/models

# 非串流
curl -s -H "Authorization: Bearer $API_SECRET" \
  -H "Content-Type: application/json" \
  -H "X-OpenWebUI-Chat-Id: demo-chat-1" \
  -d '{"model":"xiaochenguang","stream":false,"messages":[{"role":"user","content":"你好"}]}' \
  https://<HOST>/v1/chat/completions
```
