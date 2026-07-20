<template>
  <div v-if="visible" class="login-overlay" @click.self="onBackdrop">
    <div class="login-card">
      <div class="login-header">
        <div class="login-icon">✨</div>
        <h2>{{ mode === 'signin' ? '登入小宸光' : '建立帳號' }}</h2>
        <p class="login-sub">
          Email 登入後，個人記憶與人格會跨裝置同步
        </p>
      </div>

      <form class="login-form" @submit.prevent="submit">
        <label class="field">
          <span>Email</span>
          <input
            v-model.trim="email"
            type="email"
            required
            autocomplete="email"
            placeholder="you@example.com"
            :disabled="loading"
          />
        </label>

        <label class="field">
          <span>密碼</span>
          <input
            v-model="password"
            type="password"
            required
            minlength="6"
            autocomplete="current-password"
            placeholder="至少 6 碼"
            :disabled="loading"
          />
        </label>

        <p v-if="error" class="error-msg">{{ error }}</p>
        <p v-if="info" class="info-msg">{{ info }}</p>

        <button type="submit" class="primary-btn" :disabled="loading || !email || !password">
          {{ loading ? '處理中...' : (mode === 'signin' ? '登入' : '註冊') }}
        </button>
      </form>

      <div class="login-footer">
        <button type="button" class="link-btn" :disabled="loading" @click="toggleMode">
          {{ mode === 'signin' ? '還沒有帳號？註冊' : '已有帳號？登入' }}
        </button>
        <button type="button" class="link-btn ghost" :disabled="loading" @click="$emit('close')">
          稍後再說（訪客模式）
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { signInWithEmail, signUpWithEmail, isAuthConfigured } from '../lib/auth.js'

export default {
  name: 'LoginModal',
  props: {
    visible: { type: Boolean, default: false },
  },
  emits: ['close', 'success'],
  data() {
    return {
      mode: 'signin', // signin | signup
      email: '',
      password: '',
      loading: false,
      error: '',
      info: '',
    }
  },
  watch: {
    visible(val) {
      if (val) {
        this.error = ''
        this.info = ''
        if (!isAuthConfigured()) {
          this.error = '尚未設定 VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY，無法登入'
        }
      }
    },
  },
  methods: {
    toggleMode() {
      this.mode = this.mode === 'signin' ? 'signup' : 'signin'
      this.error = ''
      this.info = ''
    },
    onBackdrop() {
      if (!this.loading) this.$emit('close')
    },
    async submit() {
      this.error = ''
      this.info = ''
      if (!isAuthConfigured()) {
        this.error = '尚未設定 Supabase 環境變數'
        return
      }
      this.loading = true
      try {
        if (this.mode === 'signin') {
          const data = await signInWithEmail(this.email, this.password)
          this.$emit('success', { type: 'signin', session: data.session, user: data.user })
        } else {
          const data = await signUpWithEmail(this.email, this.password)
          // 若專案開啟 Email 確認，session 可能為 null
          if (!data.session) {
            this.info = '註冊成功！若需驗證 Email，請至信箱點擊連結後再登入。'
            this.mode = 'signin'
          } else {
            this.$emit('success', { type: 'signup', session: data.session, user: data.user })
          }
        }
      } catch (e) {
        this.error = e?.message || '登入失敗，請稍後再試'
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.login-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.25);
  padding: 1.75rem 1.5rem 1.25rem;
  text-align: left;
}

.login-header {
  text-align: center;
  margin-bottom: 1.25rem;
}

.login-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.login-header h2 {
  margin: 0;
  font-size: 1.35rem;
  color: #1f2937;
}

.login-sub {
  margin: 0.4rem 0 0;
  font-size: 0.85rem;
  color: #6b7280;
  line-height: 1.4;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: #374151;
  font-weight: 600;
}

.field input {
  padding: 0.7rem 0.85rem;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 400;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.field input:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
}

.primary-btn {
  margin-top: 0.25rem;
  padding: 0.75rem 1rem;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
  transition: transform 0.15s, opacity 0.15s;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-msg {
  margin: 0;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
  font-size: 0.85rem;
}

.info-msg {
  margin: 0;
  color: #065f46;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
  font-size: 0.85rem;
}

.login-footer {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  align-items: center;
}

.link-btn {
  background: none;
  border: none;
  color: #667eea;
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0.35rem;
}

.link-btn.ghost {
  color: #9ca3af;
}

.link-btn:hover:not(:disabled) {
  text-decoration: underline;
}
</style>
