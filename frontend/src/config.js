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

// 選擇性 API Secret（若後端有設定 API_SECRET，前端需帶此 token）
export const API_SECRET = import.meta.env.VITE_API_SECRET || ''

// 取得帶有 Auth 的通用請求 headers
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
