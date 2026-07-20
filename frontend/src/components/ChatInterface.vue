<template>
  <div class="chat-page">
    <div class="chat-card">
      
      <!-- 標題欄 -->
      <div class="header">
        <div class="header-left">
          <div class="logo-icon">✨</div>
          <div class="header-text">
            <h1>小宸光 AI</h1>
            <p>靈魂孵化器系統</p>
          </div>
        </div>
        <div class="header-right">
          <div
            class="token-chip"
            :title="tokenTooltip"
            @click="refreshUsageSummary"
          >
            <span class="token-label">🪙 Token</span>
            <span class="token-value">{{ tokenChipText }}</span>
          </div>
          <div v-if="authUser" class="user-chip" :title="authUser.email || authUser.id">
            <span class="user-dot"></span>
            <span class="user-label">{{ authEmailLabel }}</span>
          </div>
          <button
            v-if="authUser"
            @click="handleLogout"
            class="status-btn auth-btn"
            type="button"
          >
            登出
          </button>
          <button
            v-else
            @click="showLoginModal = true"
            class="status-btn auth-btn"
            type="button"
          >
            🔐 登入
          </button>
          <button @click="goToHealthCheck" class="status-btn" type="button">
            📋 系統狀態
          </button>
        </div>
      </div>

      <!-- 主內容區 -->
      <div class="main-content">
        
        <!-- 聊天區域 -->
        <div class="chat-section">
          
          <!-- 訊息區域 -->
          <div ref="messagesArea" class="messages-area">
            <div 
              v-for="(msg, index) in messages" 
              :key="index" 
              :class="['message-wrapper', `message-${msg.type}`]"
            >
              <div class="message-bubble">
                <p :class="['message-text', { streaming: msg.streaming }]">{{ msg.content }}</p>
                <div class="message-footer">
                  <span v-if="msg.emotion" class="emotion-tag">
                    {{ getEmotionEmoji(msg.emotion.dominant_emotion) }}
                    {{ msg.emotion.dominant_emotion }}
                  </span>
                  <span v-if="msg.usage" class="usage-tag" :title="formatUsageDetail(msg.usage)">
                    🪙 in {{ msg.usage.prompt_tokens || 0 }} / out {{ msg.usage.completion_tokens || 0 }}
                    · ${{ formatCost(msg.usage.cost_usd) }}
                  </span>
                  <small class="timestamp">{{ msg.timestamp }}</small>
                </div>
              </div>
            </div>
            
            <!-- Loading：僅在等待第一個串流 token 時顯示 -->
            <div v-if="isLoading && !isStreaming" class="message-wrapper message-assistant">
              <div class="message-bubble">
                <div class="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span class="loading-text">小宸光正在思考...</span>
              </div>
            </div>
          </div>

          <!-- 功能按鈕區（修正：flex-wrap 響應式） -->
          <div class="action-buttons-wrapper">
            <div class="action-buttons">
              <label class="action-btn upload-btn">
                <span class="btn-icon">📎</span>
                <span class="btn-text">上傳檔案</span>
                <input 
                  type="file" 
                  @change="handleFileUpload" 
                  style="display: none;" 
                  accept=".txt,.md,.json,.pdf,.docx,.png,.jpg,.jpeg"
                  multiple
                />
              </label>
              
              <button @click="openCopilotWindow" class="action-btn copilot-btn">
                <span class="btn-icon">🤖</span>
                <span class="btn-text">Ask Copilot</span>
              </button>
              
              <button @click="archiveConversation" class="action-btn archive-btn">
                <span class="btn-icon">🗂️</span>
                <span class="btn-text">結束對話</span>
              </button>
            </div>
          </div>

          <!-- Token 用量列 -->
          <div v-if="lastUsage || usageSummary" class="token-bar">
            <div class="token-bar-left">
              <span v-if="lastUsage">
                本次：輸入 <b>{{ lastUsage.prompt_tokens || 0 }}</b>
                · 輸出 <b>{{ lastUsage.completion_tokens || 0 }}</b>
                · 成本 <b>${{ formatCost(lastUsage.cost_usd) }}</b>
              </span>
              <span v-else>尚未產生 Token 用量</span>
            </div>
            <div class="token-bar-right" v-if="usageSummary">
              今日：{{ usageSummary.total_tokens || 0 }} tokens
              · ${{ formatCost(usageSummary.cost_usd) }}
              / ${{ formatCost(usageSummary.budget_usd) }}
              <span class="remaining">(剩 ${{ formatCost(usageSummary.remaining_usd) }})</span>
            </div>
          </div>

          <!-- 輸入區域 -->
          <div class="input-wrapper">
            <input
              v-model="userInput"
              @keyup.enter="sendMessage"
              :disabled="isLoading"
              placeholder="輸入您的訊息..."
              class="message-input"
            />
            <button
              @click="sendMessage"
              :disabled="isLoading || !userInput.trim()"
              class="send-button"
            >
              <span class="btn-icon">💬</span>
              <span class="btn-text">{{ isLoading ? '發送中...' : '發送' }}</span>
            </button>
          </div>
        </div>

        <!-- 側邊欄 - 反思區塊 -->
        <div class="sidebar">
          <div class="reflection-card">
            <h3 class="sidebar-title">
              <span class="title-icon">💭</span>
              <span>AI 反思</span>
            </h3>
            
            <div v-if="latestReflection" class="reflection-content">
              <div v-if="latestReflection.summary" class="reflection-summary">
                {{ latestReflection.summary }}
              </div>
              
              <div v-if="latestReflection.causes && latestReflection.causes.length > 0" class="reflection-causes">
                <div class="causes-title">
                  <span>🔍</span>
                  <span>原因分析</span>
                </div>
                <div class="cause-list">
                  <div 
                    v-for="(cause, idx) in latestReflection.causes" 
                    :key="idx" 
                    class="cause-item"
                  >
                    {{ cause }}
                  </div>
                </div>
              </div>
            </div>
            
            <div v-else class="empty-state">
              <div class="empty-icon">💭</div>
              <p>暫無反思數據</p>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Copilot 視窗 -->
    <CopilotWindow
      :visible="copilotWindowVisible"
      :conversation-id="conversationId"
      :user-id="userId"
      @close="closeCopilotWindow"
    />

    <!-- Email 登入 -->
    <LoginModal
      :visible="showLoginModal"
      @close="showLoginModal = false"
      @success="onLoginSuccess"
    />
  </div>
</template>

<script>
import axios from 'axios'
import { CHAT_API, API_BASE, API_SECRET, getAuthHeaders } from '../config.js'
import CopilotWindow from './CopilotWindow.vue'
import LoginModal from './LoginModal.vue'
import {
  getSession,
  getUserAuthHeaders,
  onAuthStateChange,
  resolveUserId,
  signOut,
  syncUserProfile,
  isAuthConfigured,
} from '../lib/auth.js'

const getApiUrl = () => {
  const url = import.meta.env.VITE_API_URL
  console.log('🔗 [ChatInterface] API URL 環境變數:', url)
  
  if (!url || url === 'undefined' || url === 'null') {
    console.warn('⚠️ [ChatInterface] VITE_API_URL 未定義，使用預設 Replit URL')
    return 'https://ai2.dreamground.net'
  }
  
  return url.replace(/\/$/, '')
}

const API_URL = getApiUrl()
console.log('🚀 [ChatInterface] 最終 API_URL:', API_URL)

export default {
  name: 'ChatInterface',
  components: {
    CopilotWindow,
    LoginModal,
  },
  data() {
    return {
      messages: this.loadMessagesFromStorage(),
      userInput: '',
      isLoading: false,
      isStreaming: false,
      streamAbortController: null,
      memories: [],
      emotionalStates: [],
      latestReflection: null,
      conversationId: this.getOrCreateConversationId(),
      userId: this.getOrCreateUserId(),
      copilotWindowVisible: false,
      showLoginModal: false,
      authUser: null,
      authUnsubscribe: null,
      personalitySummary: null,
      lastUsage: null,
      usageSummary: null,
    }
  },
  computed: {
    authEmailLabel() {
      if (!this.authUser) return ''
      const email = this.authUser.email || ''
      if (email.length > 22) return email.slice(0, 18) + '…'
      return email || '已登入'
    },
    tokenChipText() {
      if (this.lastUsage && (this.lastUsage.total_tokens || this.lastUsage.prompt_tokens)) {
        const t =
          this.lastUsage.total_tokens ||
          (this.lastUsage.prompt_tokens || 0) + (this.lastUsage.completion_tokens || 0)
        return `${t} · $${this.formatCost(this.lastUsage.cost_usd)}`
      }
      if (this.usageSummary) {
        return `今日 ${this.usageSummary.total_tokens || 0}`
      }
      return '—'
    },
    tokenTooltip() {
      const parts = []
      if (this.lastUsage) {
        parts.push(
          `本次 in ${this.lastUsage.prompt_tokens || 0} / out ${this.lastUsage.completion_tokens || 0} / $${this.formatCost(this.lastUsage.cost_usd)}`
        )
      }
      if (this.usageSummary) {
        parts.push(
          `今日 $${this.formatCost(this.usageSummary.cost_usd)} / 預算 $${this.formatCost(this.usageSummary.budget_usd)}`
        )
      }
      return parts.join('\n') || 'Token 使用量（點擊重新整理）'
    },
  },
  methods: {
    formatCost(v) {
      const n = Number(v || 0)
      if (n === 0) return '0'
      if (n < 0.0001) return n.toFixed(6)
      if (n < 0.01) return n.toFixed(4)
      return n.toFixed(3)
    },
    formatUsageDetail(usage) {
      if (!usage) return ''
      return `input ${usage.prompt_tokens || 0} · output ${usage.completion_tokens || 0} · total ${usage.total_tokens || 0} · $${this.formatCost(usage.cost_usd)} · ${usage.model || ''}`
    },
    applyUsagePayload(usage) {
      if (!usage) return
      this.lastUsage = {
        prompt_tokens: usage.prompt_tokens || 0,
        completion_tokens: usage.completion_tokens || 0,
        total_tokens:
          usage.total_tokens ||
          (usage.prompt_tokens || 0) + (usage.completion_tokens || 0),
        cost_usd: usage.cost_usd || 0,
        model: usage.model || '',
      }
      if (usage.daily) {
        this.usageSummary = usage.daily
      }
    },
    extractStreamMeta(fullText) {
      const marker = '\n__XCG_META__'
      const idx = fullText.lastIndexOf(marker)
      if (idx === -1) {
        // 也可能沒有換行前綴
        const alt = fullText.lastIndexOf('__XCG_META__')
        if (alt === -1) return { text: fullText, meta: null }
        const jsonPart = fullText.slice(alt + '__XCG_META__'.length)
        try {
          return { text: fullText.slice(0, alt).replace(/\n$/, ''), meta: JSON.parse(jsonPart) }
        } catch {
          return { text: fullText, meta: null }
        }
      }
      const jsonPart = fullText.slice(idx + marker.length)
      try {
        return { text: fullText.slice(0, idx), meta: JSON.parse(jsonPart) }
      } catch {
        return { text: fullText, meta: null }
      }
    },
    async refreshUsageSummary() {
      try {
        const headers = await this.buildRequestHeaders()
        const response = await axios.get(
          `${API_URL}/api/usage/summary?user_id=${encodeURIComponent(this.userId)}`,
          { headers }
        )
        if (response.data?.user) {
          this.usageSummary = {
            prompt_tokens: response.data.user.prompt_tokens,
            completion_tokens: response.data.user.completion_tokens,
            total_tokens: response.data.user.total_tokens,
            cost_usd: response.data.user.cost_usd,
            budget_usd: response.data.user.budget_usd,
            remaining_usd: response.data.user.remaining_usd,
            calls: response.data.user.calls,
          }
        } else if (response.data?.global) {
          this.usageSummary = {
            prompt_tokens: response.data.global.prompt_tokens,
            completion_tokens: response.data.global.completion_tokens,
            total_tokens: response.data.global.total_tokens,
            cost_usd: response.data.global.cost_usd,
            budget_usd: response.data.global.budget_usd,
            remaining_usd: response.data.global.remaining_usd,
            calls: response.data.global.calls,
          }
        }
      } catch (e) {
        console.warn('⚠️ 讀取 usage 失敗:', e.message)
      }
    },

    generateConversationId() {
      return 'conv_' + Date.now() + '_' + Math.random().toString(36).substring(7)
    },
    getOrCreateUserId() {
      // 優先使用已登入綁定的 id；否則建立/沿用訪客 id
      let uid = localStorage.getItem('xiaochenguang_user_id')
      if (!uid) {
        uid = resolveUserId(null)
        console.log('🆕 [UserId] 建立訪客 ID:', uid)
      } else {
        console.log('✅ [UserId] 載入已存在的使用者 ID:', uid)
      }
      return uid
    },
    async buildRequestHeaders() {
      // 已登入：帶 Supabase JWT；否則回退 API_SECRET
      try {
        return await getUserAuthHeaders()
      } catch {
        return getAuthHeaders()
      }
    },
    getOrCreateConversationId() {
      // 同一個用戶回來繼續同一個對話，除非主動「結束對話」
      let cid = localStorage.getItem('xiaochenguang_conversation_id')
      if (!cid) {
        cid = this.generateConversationId()
        localStorage.setItem('xiaochenguang_conversation_id', cid)
        console.log('🆕 [ConvId] 建立新對話 ID:', cid)
      } else {
        console.log('✅ [ConvId] 繼續上次的對話:', cid)
      }
      return cid
    },
    loadMessagesFromStorage() {
      // 從 localStorage 載入上次的對話記錄
      try {
        const saved = localStorage.getItem('xiaochenguang_messages')
        if (saved) {
          const msgs = JSON.parse(saved)
          console.log(`✅ [Messages] 載入 ${msgs.length} 則對話記錄`)
          return msgs
        }
      } catch (e) {
        console.warn('⚠️ [Messages] 載入對話記錄失敗，重新開始')
      }
      return []
    },
    saveMessagesToStorage() {
      // 把對話記錄存進 localStorage（最多保留最近 100 則）
      try {
        const toSave = this.messages.slice(-100)
        localStorage.setItem('xiaochenguang_messages', JSON.stringify(toSave))
      } catch (e) {
        console.warn('⚠️ [Messages] 儲存對話記錄失敗:', e.message)
      }
    },
    scrollToBottom() {
      this.$nextTick(() => {
        if (this.$refs.messagesArea) {
          this.$refs.messagesArea.scrollTop = this.$refs.messagesArea.scrollHeight
        }
      })
    },
    getEmotionEmoji(emotion) {
      const emojiMap = {
        'joy': '😊',
        'sadness': '😢',
        'anger': '😠',
        'fear': '😨',
        'surprise': '😮',
        'disgust': '🤢',
        'trust': '😌',
        'anticipation': '🤔',
        'neutral': '😐'
      }
      return emojiMap[emotion] || '😐'
    },
    async sendMessage() {
      if (!this.userInput.trim() || this.isLoading || this.isStreaming) return

      // 取消上一次未完成的串流（理論上已阻擋，雙保險）
      if (this.streamAbortController) {
        this.streamAbortController.abort()
      }
      this.streamAbortController = new AbortController()

      this.isLoading = true
      this.isStreaming = false

      this.messages.push({
        type: 'user',
        content: this.userInput,
        timestamp: new Date().toLocaleTimeString('zh-TW')
      })

      const userMessage = this.userInput
      this.userInput = ''
      this.scrollToBottom()

      // 空的 assistant 佔位，串流 token 會即時寫入
      const assistantMsgIndex = this.messages.length
      this.messages.push({
        type: 'assistant',
        content: '',
        emotion: null,
        timestamp: new Date().toLocaleTimeString('zh-TW'),
        streaming: true
      })

      try {
        // stream=true：OpenAI 真實串流；use_tools=true：保留 web_search 等工具
        const response = await fetch(
          `${API_URL}/api/chat?stream=true&use_tools=true`,
          {
            method: 'POST',
            headers: await this.buildRequestHeaders(),
            signal: this.streamAbortController.signal,
            body: JSON.stringify({
              user_message: userMessage,
              conversation_id: this.conversationId,
              user_id: this.userId
            })
          }
        )

        if (!response.ok) {
          const errText = await response.text().catch(() => '')
          let detail = errText
          try {
            const j = JSON.parse(errText)
            if (j?.detail?.message) detail = j.detail.message
            else if (typeof j?.detail === 'string') detail = j.detail
            else if (j?.message) detail = j.message
          } catch (_) { /* plain text */ }
          if (response.status === 429) {
            throw new Error(`預算已用盡：${detail}`)
          }
          if (response.status === 400 && /blocked|審核|moderation/i.test(detail + errText)) {
            throw new Error(detail || '內容未通過安全審核')
          }
          throw new Error(`HTTP ${response.status}${detail ? ': ' + String(detail).slice(0, 160) : ''}`)
        }

        if (!response.body) {
          throw new Error('瀏覽器不支援串流回應（ReadableStream）')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let fullText = ''
        let receivedFirstChunk = false

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          if (!chunk) continue

          if (!receivedFirstChunk) {
            receivedFirstChunk = true
            this.isStreaming = true
            this.isLoading = false
          }

          fullText += chunk
          // 即時更新：隱藏尚未完整的 meta 尾端
          const live = this.extractStreamMeta(fullText)
          this.messages[assistantMsgIndex].content = live.text
          this.scrollToBottom()
        }

        // flush 解碼器殘餘
        const tail = decoder.decode()
        if (tail) {
          fullText += tail
        }

        const { text: cleanText, meta } = this.extractStreamMeta(fullText)
        this.messages[assistantMsgIndex].content = cleanText
        this.messages[assistantMsgIndex].streaming = false

        if (meta?.usage) {
          this.applyUsagePayload(meta.usage)
          this.messages[assistantMsgIndex].usage = {
            prompt_tokens: meta.usage.prompt_tokens,
            completion_tokens: meta.usage.completion_tokens,
            total_tokens: meta.usage.total_tokens,
            cost_usd: meta.usage.cost_usd,
            model: meta.usage.model,
          }
        }
        if (meta?.blocked) {
          this.messages[assistantMsgIndex].type = 'system'
        }

        if (!cleanText.trim()) {
          this.messages[assistantMsgIndex].content = '（沒有收到回覆內容，請再試一次）'
        } else if (cleanText.startsWith('[ERROR]')) {
          this.messages[assistantMsgIndex].type = 'system'
        }

        // 後端背景任務會存記憶；稍後刷新側欄
        this.loadMemories()
        this.loadEmotionalStates()
        this.refreshUsageSummary()

      } catch (error) {
        if (error.name === 'AbortError') {
          this.messages[assistantMsgIndex].content =
            (this.messages[assistantMsgIndex].content || '') + '\n（串流已中斷）'
        } else {
          this.messages[assistantMsgIndex].type = 'system'
          this.messages[assistantMsgIndex].content = `❌ 發生錯誤: ${error.message}`
        }
        this.messages[assistantMsgIndex].streaming = false
        this.scrollToBottom()
      } finally {
        this.isLoading = false
        this.isStreaming = false
        this.streamAbortController = null
        this.scrollToBottom()
        this.saveMessagesToStorage()
      }
    },

    async loadHistoryFromBackend() {
      // 從後端 Supabase 載入歷史對話（用於 localStorage 空的情況，如換裝置/清快取）
      try {
        const headers = await this.buildRequestHeaders()
        const response = await axios.get(
          `${API_URL}/api/recent-history/${this.userId}?limit=30`,
          { headers }
        )
        const { messages, conversation_id } = response.data

        if (messages && messages.length > 0) {
          this.messages = messages
          // 如果後端有回傳 conversation_id，延續那個對話
          if (conversation_id) {
            this.conversationId = conversation_id
            localStorage.setItem('xiaochenguang_conversation_id', conversation_id)
          }
          this.saveMessagesToStorage()
          console.log(`✅ [History] 從後端載入 ${messages.length} 則歷史對話`)
        }
      } catch (error) {
        // 載入失敗不影響正常使用
        console.warn('⚠️ [History] 從後端載入歷史失敗，以空白對話開始:', error.message)
      }
    },
    async loadPersonality() {
      try {
        const headers = await this.buildRequestHeaders()
        const response = await axios.get(
          `${API_URL}/api/personality/${this.userId}`,
          { headers }
        )
        this.personalitySummary = response.data?.personality || null
        if (this.personalitySummary) {
          console.log('✅ [Personality] 已載入個人人格')
        }
      } catch (error) {
        this.personalitySummary = null
        console.warn('⚠️ [Personality] 載入失敗:', error.message)
      }
    },
    /**
     * 登入後：用 JWT 一次同步記憶 + 人格（跨裝置）
     * @param {{ notify?: boolean }} options notify=false 時不插入系統提示（頁面重載）
     */
    async applyAuthSync(options = {}) {
      const notify = options.notify !== false
      try {
        const data = await syncUserProfile()
        this.userId = data.user_id
        localStorage.setItem('xiaochenguang_user_id', data.user_id)

        if (data.conversation_id) {
          this.conversationId = data.conversation_id
          localStorage.setItem('xiaochenguang_conversation_id', data.conversation_id)
        }

        if (data.messages && data.messages.length > 0) {
          this.messages = data.messages
          this.saveMessagesToStorage()
        }

        this.personalitySummary = data.personality || null

        if (notify) {
          const traitHint = data.personality?.traits
            ? Object.keys(data.personality.traits).slice(0, 3).join('、')
            : ''
          this.messages.push({
            type: 'system',
            content:
              `🔐 已登入並同步個人資料` +
              (data.message_count ? `（${data.message_count} 筆記憶）` : '') +
              (traitHint ? `\n🎭 人格特質已載入：${traitHint}` : '\n🎭 人格資料已就緒'),
            timestamp: new Date().toLocaleTimeString('zh-TW'),
          })
          this.scrollToBottom()
        }

        await this.loadMemories()
        await this.loadEmotionalStates()
        console.log('✅ [Auth] 跨裝置同步完成')
      } catch (error) {
        console.warn('⚠️ [Auth] 同步失敗，改走一般歷史載入:', error.message)
        await this.loadHistoryFromBackend()
        await this.loadPersonality()
      }
    },
    async onLoginSuccess({ user }) {
      this.showLoginModal = false
      this.authUser = user || null
      if (user?.id) {
        this.userId = user.id
        localStorage.setItem('xiaochenguang_user_id', user.id)
      }
      // 登入後強制從雲端載入，避免舊裝置 local 訊息覆蓋
      localStorage.removeItem('xiaochenguang_messages')
      this.messages = []
      await this.applyAuthSync({ notify: true })
    },
    async handleLogout() {
      try {
        await signOut()
      } catch (e) {
        console.warn('登出時發生錯誤:', e.message)
      }
      this.authUser = null
      this.personalitySummary = null
      this.userId = resolveUserId(null)
      this.messages.push({
        type: 'system',
        content: '👋 已登出。訪客模式下對話不會跨裝置同步。',
        timestamp: new Date().toLocaleTimeString('zh-TW'),
      })
      this.scrollToBottom()
    },
    async loadMemories() {
      try {
        const headers = await this.buildRequestHeaders()
        const response = await axios.get(
          `${API_URL}/api/memories/${this.conversationId}?limit=10`,
          { headers }
        )
        this.memories = response.data
      } catch (error) {
        this.memories = []
      }
    },
    async loadEmotionalStates() {
      try {
        const headers = await this.buildRequestHeaders()
        const response = await axios.get(
          `${API_URL}/api/emotional-states/${this.userId}?limit=10`,
          { headers }
        )
        this.emotionalStates = response.data
      } catch (error) {
        this.emotionalStates = []
      }
    },
    async handleFileUpload(event) {
      const files = Array.from(event.target.files)
      if (!files.length) return

      for (const file of files) {
        try {
          this.messages.push({
            type: 'system',
            content: `⏳ 正在上傳檔案 "${file.name}"...`,
            timestamp: new Date().toLocaleTimeString('zh-TW')
          })
          this.scrollToBottom()

          const formData = new FormData()
          formData.append('file', file)
          formData.append('conversation_id', this.conversationId)
          formData.append('user_id', this.userId)

          const response = await axios.post(`${API_URL}/api/upload_file`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
          })

          const summary = response.data.summary || '檔案已上傳'
          const fileType = response.data.file_type || ''
          const parsed = response.data.parsed ? '✅ 已解析' : '⚠️ 未解析'

          this.messages.push({
            type: 'system',
            content: `📎 檔案上傳成功\n📄 ${file.name} (${fileType})\n${parsed}\n📝 ${summary}`,
            timestamp: new Date().toLocaleTimeString('zh-TW')
          })
          this.scrollToBottom()

          if (response.data.ai_analysis) {
            this.messages.push({
              type: 'assistant',
              content: response.data.ai_analysis,
              timestamp: new Date().toLocaleTimeString('zh-TW')
            })
            this.scrollToBottom()
          }
        } catch (error) {
          this.messages.push({
            type: 'system',
            content: `❌ 「${file.name}」上傳失敗: ${error.response?.data?.detail || error.message}`,
            timestamp: new Date().toLocaleTimeString('zh-TW')
          })
          this.scrollToBottom()
        }
      }

      event.target.value = ''
    },
    openCopilotWindow() {
      console.log('🤖 開啟 Copilot 視窗')
      this.copilotWindowVisible = true
    },
    closeCopilotWindow() {
      console.log('🤖 關閉 Copilot 視窗')
      this.copilotWindowVisible = false
    },
    async archiveConversation() {
      if (!confirm('確定要結束此對話並開始新對話嗎？')) {
        return
      }

      try {
        // 嘗試封存到 IPFS（失敗不影響開新對話）
        this.messages.push({
          type: 'system',
          content: '⏳ 正在封存對話...',
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
        this.scrollToBottom()

        try {
          const response = await axios.post(`${API_URL}/api/archive_conversation`, {
            conversation_id: this.conversationId,
            user_id: this.userId,
            include_attachments: true
          })
          const cid = response.data.ipfs_cid
          if (cid) {
            this.messages.push({
              type: 'system',
              content: `✅ 對話已封存\n🔗 CID: ${cid}`,
              timestamp: new Date().toLocaleTimeString('zh-TW')
            })
          }
        } catch (archiveErr) {
          console.warn('⚠️ 封存失敗，但仍開始新對話:', archiveErr.message)
        }

        // 清除 localStorage，開始新對話
        localStorage.removeItem('xiaochenguang_messages')
        localStorage.removeItem('xiaochenguang_conversation_id')

        // 重置對話狀態
        this.messages = []
        this.conversationId = this.getOrCreateConversationId()
        this.messages.push({
          type: 'system',
          content: '✨ 已開始新對話，小宸光在這裡陪你～',
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
        this.scrollToBottom()

      } catch (error) {
        this.messages.push({
          type: 'system',
          content: `❌ 操作失敗: ${error.message}`,
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
        this.scrollToBottom()
      }
    },
    handleBeforeUnload(event) {
      if (this.messages.length > 2) {
        event.preventDefault()
        event.returnValue = '你有未封存的對話，確定要離開嗎？'
      }
    },
    goToHealthCheck() {
      window.open('/status', '_blank')
    }
  },
  async mounted() {
    // 初始化 Auth 狀態
    try {
      const session = await getSession()
      if (session?.user) {
        this.authUser = session.user
        this.userId = session.user.id
        localStorage.setItem('xiaochenguang_user_id', session.user.id)
        // 已登入：自動同步記憶與人格（跨裝置），重載不重複提示
        await this.applyAuthSync({ notify: false })
      } else if (this.messages.length === 0) {
        await this.loadHistoryFromBackend()
      }
    } catch (e) {
      console.warn('⚠️ [Auth] 初始化失敗:', e.message)
      if (this.messages.length === 0) {
        await this.loadHistoryFromBackend()
      }
    }

    this.authUnsubscribe = onAuthStateChange(async (session) => {
      if (session?.user) {
        // 避免與 onLoginSuccess 重複同步：僅在 user 變更時處理
        if (!this.authUser || this.authUser.id !== session.user.id) {
          this.authUser = session.user
          this.userId = session.user.id
          localStorage.setItem('xiaochenguang_user_id', session.user.id)
        } else {
          this.authUser = session.user
        }
      } else {
        this.authUser = null
      }
    })

    // 未登入且 Auth 已設定時，輕量提示可登入同步
    if (!this.authUser && isAuthConfigured() && this.messages.length === 0) {
      this.messages.push({
        type: 'system',
        content: '💡 登入後可跨裝置同步個人記憶與人格～點右上角「登入」開始。',
        timestamp: new Date().toLocaleTimeString('zh-TW'),
      })
    }

    this.loadMemories()
    this.loadEmotionalStates()
    this.refreshUsageSummary()
    if (this.authUser) {
      this.loadPersonality()
    }
    this.$nextTick(() => this.scrollToBottom())
    window.addEventListener('beforeunload', this.handleBeforeUnload)
  },

  beforeUnmount() {
    window.removeEventListener('beforeunload', this.handleBeforeUnload)
    if (typeof this.authUnsubscribe === 'function') {
      this.authUnsubscribe()
    }
  }
}
</script>

<style scoped>
/* 全局容器 */
.chat-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 50%, #dfe6f0 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.chat-card {
  width: 100%;
  max-width: 1400px;
  height: 90vh;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 標題欄 */
.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1.25rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.logo-icon {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
}

.header-text h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
}

.header-text p {
  margin: 0;
  font-size: 0.75rem;
  opacity: 0.9;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  max-width: 180px;
}

.user-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6ee7b7;
  flex-shrink: 0;
}

.user-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-btn {
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 12px;
  color: white;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 0.9rem;
}

.status-btn.auth-btn {
  background: rgba(255, 255, 255, 0.28);
}

.status-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}

.token-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1rem;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 12px;
  padding: 0.35rem 0.7rem;
  font-size: 0.72rem;
  cursor: pointer;
  max-width: 140px;
  line-height: 1.2;
}

.token-chip:hover {
  background: rgba(255, 255, 255, 0.28);
}

.token-label {
  opacity: 0.9;
  font-weight: 600;
}

.token-value {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.usage-tag {
  font-size: 0.7rem;
  opacity: 0.75;
  background: rgba(102, 126, 234, 0.1);
  color: #4c51bf;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
}

.message-assistant .usage-tag {
  color: #5b21b6;
}

.token-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.45rem 1.25rem;
  font-size: 0.78rem;
  color: #4b5563;
  background: linear-gradient(90deg, rgba(102, 126, 234, 0.08), rgba(118, 75, 162, 0.08));
  border-top: 1px solid #e5e7eb;
}

.token-bar b {
  color: #4338ca;
  font-weight: 700;
}

.token-bar .remaining {
  color: #059669;
  margin-left: 0.25rem;
}


/* 主內容區 */
.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 聊天區域 */
.chat-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: linear-gradient(to bottom, transparent, rgba(249, 250, 251, 0.5));
}

/* 訊息區域 */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message-wrapper {
  display: flex;
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-user {
  justify-content: flex-end;
}

.message-assistant {
  justify-content: flex-start;
}

.message-system {
  justify-content: center;
}

.message-bubble {
  max-width: 70%;
  padding: 1rem 1.25rem;
  border-radius: 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.message-user .message-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.message-assistant .message-bubble {
  background: white;
  color: #1f2937;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 4px;
}

.message-system .message-bubble {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  text-align: center;
  max-width: 90%;
}

.message-text {
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.message-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.5rem;
  gap: 0.5rem;
}

.emotion-tag {
  font-size: 0.75rem;
  opacity: 0.8;
}

.timestamp {
  font-size: 0.7rem;
  opacity: 0.6;
  margin-left: auto;
}

/* Loading 動畫 */
.loading-dots {
  display: flex;
  gap: 0.35rem;
  margin-bottom: 0.5rem;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.loading-text {
  font-size: 0.9rem;
  color: #6b7280;
}

/* Streaming 打字游標效果 */
.message-text.streaming::after {
  content: '▍';
  display: inline-block;
  animation: blink 0.7s infinite;
  color: #667eea;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 功能按鈕區（修正：flex-wrap 響應式） */
.action-buttons-wrapper {
  padding: 0.75rem 1.5rem;
  background: rgba(249, 250, 251, 0.8);
  border-top: 1px solid #e5e7eb;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.75rem;
}

.action-btn {
  padding: 0.65rem 1.25rem;
  border: none;
  border-radius: 14px;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  color: white;
}

.upload-btn {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.copilot-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.archive-btn {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.action-btn:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}

.action-btn:active {
  transform: translateY(0) scale(1);
}

.btn-icon {
  font-size: 1.1rem;
}

/* 輸入區域 */
.input-wrapper {
  padding: 1rem 1.5rem;
  background: white;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.message-input {
  flex: 1;
  padding: 0.85rem 1.25rem;
  background: #f3f4f6;
  border: 2px solid transparent;
  border-radius: 18px;
  font-size: 1rem;
  outline: none;
  transition: all 0.3s;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
}

.message-input:focus {
  background: white;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.send-button {
  padding: 0.85rem 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 18px;
  color: white;
  font-weight: 700;
  font-size: 0.95rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: 0 4px 14px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.send-button:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.send-button:disabled {
  background: #d1d5db;
  cursor: not-allowed;
  box-shadow: none;
}

.send-button:active:not(:disabled) {
  transform: translateY(0) scale(1);
}

/* 側邊欄 */
.sidebar {
  width: 320px;
  background: linear-gradient(to bottom, #eef2ff, #e0e7ff);
  border-left: 1px solid #c7d2fe;
  padding: 1.5rem;
  overflow-y: auto;
}

.reflection-card {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 1.25rem;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
}

.sidebar-title {
  margin: 0 0 1rem 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #4c1d95;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.title-icon {
  font-size: 1.3rem;
}

.reflection-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.reflection-summary {
  font-size: 0.9rem;
  line-height: 1.6;
  color: #374151;
  background: #dbeafe;
  padding: 0.85rem;
  border-radius: 12px;
  border-left: 4px solid #3b82f6;
}

.reflection-causes {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.causes-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: #4c1d95;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.cause-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.cause-item {
  font-size: 0.8rem;
  line-height: 1.4;
  color: #4b5563;
  background: white;
  padding: 0.65rem;
  padding-left: 1rem;
  border-radius: 10px;
  border-left: 3px solid #818cf8;
  position: relative;
}

.cause-item::before {
  content: "•";
  position: absolute;
  left: 0.5rem;
  color: #818cf8;
  font-weight: bold;
}

.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: #9ca3af;
}

.empty-icon {
  font-size: 3rem;
  opacity: 0.4;
  margin-bottom: 0.5rem;
}

.empty-state p {
  margin: 0;
  font-size: 0.9rem;
}

/* 響應式設計 */
@media (max-width: 1024px) {
  .sidebar {
    width: 280px;
  }
}

@media (max-width: 768px) {
  .chat-card {
    height: 100vh;
    border-radius: 0;
  }
  
  .main-content {
    flex-direction: column;
  }
  
  .sidebar {
    width: 100%;
    max-height: 200px;
    border-left: none;
    border-top: 1px solid #c7d2fe;
  }
  
  .message-bubble {
    max-width: 85%;
  }
  
  .action-buttons {
    gap: 0.5rem;
  }
  
  .btn-text {
    display: none;
  }
  
  .action-btn {
    padding: 0.65rem 1rem;
  }
  
  .send-button .btn-text {
    display: inline;
  }
}

@media (max-width: 480px) {
  .header-text h1 {
    font-size: 1.2rem;
  }
  
  .header-text p {
    font-size: 0.7rem;
  }
  
  .logo-icon {
    width: 40px;
    height: 40px;
    font-size: 1.2rem;
  }
  
  .status-btn {
    padding: 0.4rem 0.8rem;
    font-size: 0.8rem;
  }
  
  .send-button .btn-text {
    display: none;
  }
}

/* 自定義滾動條 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 10px;
}

::-webkit-scrollbar-thumb {
  background: linear-gradient(to bottom, #818cf8, #a78bfa);
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(to bottom, #6366f1, #8b5cf6);
}
</style>
