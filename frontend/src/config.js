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

console.log('📡 [Config] API_BASE:', API_BASE)
console.log('🤖 [Config] COPILOT_API_BASE:', COPILOT_API_BASE)
console.log('💬 [Config] CHAT_API:', CHAT_API)
