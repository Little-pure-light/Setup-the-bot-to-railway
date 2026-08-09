// frontend/src/config.js
const getApiBase = () => {
  const url = import.meta.env.VITE_API_URL || 'https://ai2.dreamground.net'
  return url.replace(/\/$/, '')
}

const getCopilotApiBase = () => {
  const url = import.meta.env.VITE_COPILOT_API_URL || 'https://ai2.dreamground.net:8080'
  return url.replace(/\/$/, '')
}

export const API_BASE = getApiBase()
export const COPILOT_API_BASE = getCopilotApiBase()
export const CHAT_API = `${API_BASE}/api/chat`
/** 預設走 OpenAI 真實串流（stream=true） */
export const CHAT_STREAM_API = `${API_BASE}/api/chat?stream=true&use_tools=true`

/** 語音 API */
export const VOICE_STATUS_API = `${API_BASE}/api/voice/status`
export const VOICE_PREPARE_SPEECH_API = `${API_BASE}/api/voice/prepare-speech`
export const VOICE_EVENTS_API = `${API_BASE}/api/voice/events`
export const voiceSettingsApi = (userId) =>
  `${API_BASE}/api/voice/settings/${encodeURIComponent(userId || 'default_user')}`

// 已移除對 VITE_API_SECRET 的依賴：共享 secret 不得被烤進「公開」前端 bundle
// （任何人都能從瀏覽器讀到）。前端一律改走「登入者的 Supabase JWT」，未登入即不帶 Authorization。
// 後端 API_SECRET 仍作為伺服器對伺服器/管理用途（例如 Open WebUI），不由瀏覽器前端持有。

// Supabase Auth（前端 Email 登入）
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

// 前端入口標記（可選；僅 Silence 實驗分流，預設空＝不標記）
// Cloudflare 測試部署可設 VITE_CLIENT_ID=cloudflare-test
export const CLIENT_ID = (import.meta.env.VITE_CLIENT_ID || '').trim()

/** Runtime reader (testable) for chat body client_id */
export function getClientId() {
  return (CLIENT_ID || '').trim()
}

// 取得通用請求 headers（同步版，無 Auth fallback）。
// 真正的授權一律由 lib/auth.js 的 getUserAuthHeaders() 以登入者的 Supabase JWT 提供；
// 未登入時不帶 Authorization（受保護端點會回 401，屬預期）。前端不再持有任何共享 secret。
export const getAuthHeaders = () => {
  return { 'Content-Type': 'application/json' }
}

console.log('📡 [Config] API_BASE:', API_BASE)
console.log('🤖 [Config] COPILOT_API_BASE:', COPILOT_API_BASE)
console.log('💬 [Config] CHAT_API:', CHAT_API)
console.log('🔐 [Config] Supabase Auth:', SUPABASE_URL ? 'configured' : 'not set')
