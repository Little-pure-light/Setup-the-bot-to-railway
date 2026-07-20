import { createClient } from '@supabase/supabase-js'
import { SUPABASE_URL, SUPABASE_ANON_KEY } from '../config.js'

let supabase = null

/**
 * 取得 Supabase 客戶端（未設定環境變數時回傳 null，允許訪客模式）
 */
export function getSupabase() {
  if (supabase) return supabase
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    console.warn(
      '⚠️ [Supabase] 缺少 VITE_SUPABASE_URL 或 VITE_SUPABASE_ANON_KEY，Auth 功能停用'
    )
    return null
  }
  supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storage: typeof window !== 'undefined' ? window.localStorage : undefined,
    },
  })
  return supabase
}

export function isAuthConfigured() {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY)
}
