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

// 選擇性 API Secret（若後端有設定 API_SECRET，前端需帶此 token）
export const API_SECRET = import.meta.env.VITE_API_SECRET || ''

// Supabase Auth（前端 Email 登入）
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

// 取得帶有 Auth 的通用請求 headers（同步版；優先使用 localStorage 中的 session 由呼叫端覆寫）
export const getAuthHeaders = () => {
  const headers = { 'Content-Type': 'application/json' }
  if (API_SECRET) {
    headers['Authorization'] = `Bearer ${API_SECRET}`
  }
  return headers
}

console.log('📡 [Config] API_BASE:', API_BASE)
console.log('🤖 [Config] COPILOT_API_BASE:', COPILOT_API_BASE)
console.log('💬 [Config] CHAT_API:', CHAT_API)
console.log('🔐 [Config] Supabase Auth:', SUPABASE_URL ? 'configured' : 'not set')
