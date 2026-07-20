/**
 * Supabase Auth 輔助函式（Email 登入 / 註冊 / 登出）
 */
import { getSupabase, isAuthConfigured } from './supabase.js'
import { API_BASE, API_SECRET } from '../config.js'

const USER_ID_KEY = 'xiaochenguang_user_id'
const GUEST_ID_KEY = 'xiaochenguang_guest_id'

export { isAuthConfigured }

export async function getSession() {
  const client = getSupabase()
  if (!client) return null
  const { data, error } = await client.auth.getSession()
  if (error) {
    console.warn('⚠️ [Auth] getSession:', error.message)
    return null
  }
  return data.session || null
}

export async function getCurrentUser() {
  const session = await getSession()
  return session?.user || null
}

export async function signInWithEmail(email, password) {
  const client = getSupabase()
  if (!client) throw new Error('尚未設定 Supabase（VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY）')
  const { data, error } = await client.auth.signInWithPassword({ email, password })
  if (error) throw error
  if (data.user?.id) {
    localStorage.setItem(USER_ID_KEY, data.user.id)
  }
  return data
}

export async function signUpWithEmail(email, password) {
  const client = getSupabase()
  if (!client) throw new Error('尚未設定 Supabase（VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY）')
  const { data, error } = await client.auth.signUp({ email, password })
  if (error) throw error
  if (data.user?.id) {
    localStorage.setItem(USER_ID_KEY, data.user.id)
  }
  return data
}

export async function signOut() {
  const client = getSupabase()
  if (client) {
    await client.auth.signOut()
  }
  // 登出後改回訪客 ID（保留 guest 以便未登入可用）
  const guest = localStorage.getItem(GUEST_ID_KEY)
  if (guest) {
    localStorage.setItem(USER_ID_KEY, guest)
  } else {
    localStorage.removeItem(USER_ID_KEY)
  }
}

/**
 * 訂閱登入狀態變化
 * @returns {function} unsubscribe
 */
export function onAuthStateChange(callback) {
  const client = getSupabase()
  if (!client) {
    callback(null)
    return () => {}
  }
  const { data } = client.auth.onAuthStateChange((_event, session) => {
    if (session?.user?.id) {
      localStorage.setItem(USER_ID_KEY, session.user.id)
    }
    callback(session)
  })
  return () => data.subscription.unsubscribe()
}

/**
 * 組合請求 headers：API_SECRET 或 Supabase access_token
 */
export async function getUserAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  const session = await getSession()
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`
  } else if (API_SECRET) {
    headers['Authorization'] = `Bearer ${API_SECRET}`
  }
  return headers
}

/**
 * 登入後向後端同步個人記憶與人格
 */
export async function syncUserProfile() {
  const session = await getSession()
  if (!session?.access_token) {
    throw new Error('尚未登入')
  }
  const res = await fetch(`${API_BASE}/api/auth/sync?limit=30`, {
    headers: {
      Authorization: `Bearer ${session.access_token}`,
      'Content-Type': 'application/json',
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`同步失敗 HTTP ${res.status}: ${text.slice(0, 120)}`)
  }
  return res.json()
}

/**
 * 解析目前應使用的 userId（已登入優先 Supabase UUID，否則訪客）
 */
export function resolveUserId(sessionUser) {
  if (sessionUser?.id) {
    localStorage.setItem(USER_ID_KEY, sessionUser.id)
    return sessionUser.id
  }
  let guest = localStorage.getItem(GUEST_ID_KEY)
  if (!guest) {
    guest = 'user_' + Date.now() + '_' + Math.random().toString(36).substring(5)
    localStorage.setItem(GUEST_ID_KEY, guest)
  }
  // 若尚未有正式 user_id，使用訪客
  const existing = localStorage.getItem(USER_ID_KEY)
  if (!existing || existing.startsWith('user_')) {
    localStorage.setItem(USER_ID_KEY, guest)
    return guest
  }
  return existing
}
