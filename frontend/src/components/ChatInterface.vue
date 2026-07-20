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
          <button @click="showHistoryPanel = true" class="status-btn" type="button">
            📚 歷史
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
              <div class="message-bubble" :class="{ 'has-image': msg.imageUrl }">
                <div v-if="msg.imageUrl" class="message-image-wrap">
                  <img
                    :src="msg.imageUrl"
                    :alt="msg.imageName || '上傳圖片'"
                    class="message-image"
                    @click="openImagePreview(msg.imageUrl)"
                  />
                  <div class="image-caption" v-if="msg.imageName">
                    🖼️ {{ msg.imageName }}
                    <span v-if="msg.visionModel" class="vision-badge">Vision · {{ msg.visionModel }}</span>
                  </div>
                </div>
                <p
                  v-if="msg.content"
                  :class="['message-text', { streaming: msg.streaming }]"
                >{{ msg.content }}</p>
                <div class="message-footer">
                  <span v-if="msg.emotion" class="emotion-tag">
                    {{ getEmotionEmoji(msg.emotion.dominant_emotion) }}
                    {{ msg.emotion.dominant_emotion }}
                  </span>
                  <span v-if="msg.tools_used && msg.tools_used.length" class="tools-tag" :title="formatToolsUsed(msg.tools_used)">
                    🔧 {{ msg.tools_used.map(t => toolDisplayName(t.name)).join(' · ') }}
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
            <div v-if="isLoading && !isStreaming && !toolStatusActive" class="message-wrapper message-assistant">
              <div class="message-bubble">
                <div class="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span class="loading-text">小宸光正在思考...</span>
              </div>
            </div>

            <!-- 工具使用狀態 -->
            <div v-if="toolStatusVisible" class="message-wrapper message-system">
              <div class="message-bubble tool-status-bubble" :class="'phase-' + (toolStatusPhase || 'idle')">
                <div class="tool-status-header">
                  <span class="tool-spin">{{ toolStatusPhase === 'done' || toolStatusPhase === 'skipped' ? '✨' : '🔧' }}</span>
                  <div class="tool-status-titles">
                    <strong>{{ toolStatusLabel }}</strong>
                    <span v-if="toolStatusMessage" class="tool-status-msg">{{ toolStatusMessage }}</span>
                  </div>
                  <span v-if="toolProgressText" class="tool-progress-chip">{{ toolProgressText }}</span>
                </div>
                <div v-if="toolStatusPhase === 'running' || toolStatusPhase === 'progress'" class="tool-progress-bar">
                  <div class="tool-progress-fill" :style="{ width: toolProgressPercent + '%' }"></div>
                </div>
                <div class="tool-status-list" v-if="activeTools.length">
                  <div
                    v-for="(t, i) in activeTools"
                    :key="i"
                    class="tool-status-item"
                    :class="toolItemClass(t)"
                  >
                    <span class="tool-icon">{{ t.icon || toolIcon(t.name) }}</span>
                    <span class="tool-name">{{ t.display_name || toolDisplayName(t.name) }}</span>
                    <span class="tool-args" v-if="toolArgsPreview(t)">{{ toolArgsPreview(t) }}</span>
                    <span class="tool-state" :class="toolStateClass(t)">
                      {{ toolStateLabel(t) }}
                      <template v-if="t.duration_ms != null && t.ok != null"> · {{ t.duration_ms }}ms</template>
                    </span>
                  </div>
                </div>
                <div v-if="toolErrors.length" class="tool-errors">
                  <div v-for="(err, i) in toolErrors" :key="'e'+i" class="tool-error-line">
                    ⚠️ {{ err }}
                  </div>
                </div>
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
                  accept=".txt,.md,.json,.pdf,.docx,.png,.jpg,.jpeg,.webp,.gif"
                  multiple
                />
              </label>

              <label class="action-btn vision-btn">
                <span class="btn-icon">🖼️</span>
                <span class="btn-text">圖片理解</span>
                <input
                  type="file"
                  @change="handleImageUpload"
                  style="display: none;"
                  accept="image/png,image/jpeg,image/jpg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
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

              <button
                type="button"
                class="action-btn voice-speak-btn"
                :class="{ active: autoSpeak }"
                @click="toggleAutoSpeak"
                :title="autoSpeak ? '關閉自動朗讀' : '開啟自動朗讀 AI 回覆'"
              >
                <span class="btn-icon">{{ autoSpeak ? '🔊' : '🔈' }}</span>
                <span class="btn-text">{{ autoSpeak ? '朗讀中' : '語音輸出' }}</span>
              </button>

              <button
                type="button"
                class="action-btn car-mode-btn"
                :class="{ active: carMode }"
                @click="toggleCarMode"
                :title="carMode ? '關閉車載自動語音' : '開啟車載模式（自動聽・說・送）'"
              >
                <span class="btn-icon">🚗</span>
                <span class="btn-text">{{ carMode ? '車載 ON' : '車載模式' }}</span>
              </button>
            </div>
          </div>

          <!-- 語音狀態列（車載友好） -->
          <div
            v-if="voiceSupported || carMode || isListening || isSpeaking"
            class="voice-bar"
            :class="{
              listening: isListening,
              speaking: isSpeaking,
              car: carMode,
              unsupported: !voiceSupported,
            }"
          >
            <div class="voice-bar-left">
              <span class="voice-pulse" v-if="isListening"></span>
              <span class="voice-status-icon">
                {{ isListening ? '🎙️' : isSpeaking ? '🔊' : carMode ? '🚗' : '🎧' }}
              </span>
              <span class="voice-status-text">{{ voiceStatusText }}</span>
              <span v-if="interimTranscript" class="voice-interim">「{{ interimTranscript }}」</span>
            </div>
            <div class="voice-bar-right">
              <button
                v-if="isSpeaking"
                type="button"
                class="voice-mini-btn"
                @click="stopTTS"
              >停止朗讀</button>
              <button
                v-if="isListening"
                type="button"
                class="voice-mini-btn danger"
                @click="stopListening"
              >停止收音</button>
              <span v-if="!speechRecognitionSupported" class="voice-warn">此瀏覽器不支援語音輸入</span>
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
          <div class="input-wrapper" :class="{ 'car-input': carMode }">
            <button
              type="button"
              class="mic-button"
              :class="{
                listening: isListening,
                disabled: !speechRecognitionSupported || isLoading || isStreaming,
                car: carMode,
              }"
              :disabled="!speechRecognitionSupported || isLoading || isStreaming"
              @click="toggleListening"
              :title="micButtonTitle"
            >
              <span class="mic-icon">{{ isListening ? '🟥' : '🎤' }}</span>
              <span class="mic-label">{{ isListening ? '聆聽中' : (carMode ? '按住說' : '語音') }}</span>
            </button>
            <input
              v-model="userInput"
              @keyup.enter="sendMessage"
              :disabled="isLoading"
              :placeholder="carMode ? '車載模式：說完會自動送出…' : '輸入您的訊息，或點麥克風…'"
              class="message-input"
            />
            <button
              type="button"
              class="tts-button"
              :class="{ active: isSpeaking }"
              :disabled="!speechSynthesisSupported"
              @click="speakLastAssistant"
              title="朗讀上一則 AI 回覆"
            >
              🔊
            </button>
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

    <!-- 圖片全螢幕預覽 -->
    <div
      v-if="imagePreviewUrl"
      class="image-preview-overlay"
      @click.self="imagePreviewUrl = null"
    >
      <img :src="imagePreviewUrl" alt="preview" class="image-preview-full" />
      <button type="button" class="image-preview-close" @click="imagePreviewUrl = null">關閉</button>
    </div>

    <!-- 對話歷史管理 -->
    <HistoryPanel
      :visible="showHistoryPanel"
      :user-id="userId"
      :api-base="API_URL"
      @close="showHistoryPanel = false"
      @load-conversation="onLoadHistoryConversation"
      @conversation-deleted="onHistoryConversationDeleted"
    />
  </div>
</template>

<script>
import axios from 'axios'
import {
  CHAT_API,
  API_BASE,
  API_SECRET,
  getAuthHeaders,
  VOICE_EVENTS_API,
  VOICE_PREPARE_SPEECH_API,
} from '../config.js'
import CopilotWindow from './CopilotWindow.vue'
import LoginModal from './LoginModal.vue'
import HistoryPanel from './HistoryPanel.vue'
import {
  getSession,
  getUserAuthHeaders,
  onAuthStateChange,
  resolveUserId,
  signOut,
  syncUserProfile,
  isAuthConfigured,
} from '../lib/auth.js'
import {
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  createSpeechRecognizer,
  speakText,
  stopSpeaking,
  loadVoiceSettings,
  saveVoiceSettings,
  sanitizeForSpeech,
  waitForVoices,
} from '../lib/voice.js'

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
    HistoryPanel,
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
      showHistoryPanel: false,
      authUser: null,
      authUnsubscribe: null,
      personalitySummary: null,
      lastUsage: null,
      usageSummary: null,
      activeTools: [],
      toolStatusPhase: '', // planning | running | progress | done | skipped | error | ''
      toolStatusMessage: '',
      toolStep: 0,
      toolTotal: 0,
      imagePreviewUrl: null,
      isUploadingImage: false,
      API_URL,
      // 🎙️ 語音
      speechRecognitionSupported: false,
      speechSynthesisSupported: false,
      isListening: false,
      isSpeaking: false,
      interimTranscript: '',
      finalTranscriptBuffer: '',
      autoSpeak: false,
      carMode: false,
      voiceAutoSend: true,
      voiceLang: 'zh-TW',
      voiceRate: 1.0,
      lastInputMethod: 'text',
      speechRecognizer: null,
      voiceRestartTimer: null,
      suppressAutoListen: false,
      ignoreNextListenEnd: false,
      voiceStatusHint: '',
    }
  },
  computed: {
    voiceSupported() {
      return this.speechRecognitionSupported || this.speechSynthesisSupported
    },
    voiceStatusText() {
      if (this.voiceStatusHint) return this.voiceStatusHint
      if (this.isListening) return '正在聽你說話…'
      if (this.isSpeaking) return '正在朗讀回覆…'
      if (this.carMode) return '車載模式：回覆後自動聽・說'
      if (this.autoSpeak) return '自動朗讀已開啟'
      if (!this.speechRecognitionSupported && !this.speechSynthesisSupported) {
        return '此瀏覽器不支援語音 API'
      }
      return '語音就緒'
    },
    micButtonTitle() {
      if (!this.speechRecognitionSupported) return '瀏覽器不支援語音輸入（建議 Chrome）'
      if (this.isListening) return '點擊停止收音'
      return this.carMode ? '開始語音輸入（說完自動送出）' : '開始語音輸入'
    },
    authEmailLabel() {
      if (!this.authUser) return ''
      const email = this.authUser.email || ''
      if (email.length > 22) return email.slice(0, 18) + '…'
      return email || '已登入'
    },
    toolStatusActive() {
      return ['planning', 'running', 'progress'].includes(this.toolStatusPhase)
    },
    toolStatusVisible() {
      return Boolean(this.toolStatusPhase) && this.toolStatusPhase !== 'skipped'
    },
    toolStatusLabel() {
      const map = {
        planning: '正在規劃工具…',
        running: '正在使用工具…',
        progress: '工具執行中…',
        done: '工具已完成',
        error: '工具階段異常',
        skipped: '未使用工具',
      }
      return map[this.toolStatusPhase] || '工具狀態'
    },
    toolProgressText() {
      if (this.toolTotal > 0 && this.toolStep > 0) {
        return `${this.toolStep}/${this.toolTotal}`
      }
      if (this.activeTools.length) {
        const done = this.activeTools.filter((t) => t.ok != null).length
        return `${done}/${this.activeTools.length}`
      }
      return ''
    },
    toolProgressPercent() {
      const total = this.toolTotal || this.activeTools.length || 0
      if (!total) return this.toolStatusPhase === 'planning' ? 15 : 0
      const step = this.toolStep || this.activeTools.filter((t) => t.ok != null).length
      return Math.min(100, Math.round((step / total) * 100))
    },
    toolErrors() {
      return (this.activeTools || [])
        .filter((t) => t.ok === false)
        .map((t) => {
          const name = t.display_name || this.toolDisplayName(t.name)
          return t.error ? `${name}：${t.error}` : `${name} 執行失敗`
        })
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
    toolDisplayName(name) {
      const map = {
        web_search: 'Web 搜尋',
        get_current_time: '目前時間',
        calculate: '計算機',
        get_weather: '查天氣',
        manage_reminder: '提醒',
        convert_units: '單位換算',
      }
      return map[name] || name || '工具'
    },
    toolIcon(name) {
      const map = {
        web_search: '🔍',
        get_current_time: '🕒',
        calculate: '🧮',
        get_weather: '🌤️',
        manage_reminder: '⏰',
        convert_units: '↔️',
      }
      return map[name] || '🔧'
    },
    toolArgsPreview(t) {
      const args = t?.arguments || {}
      if (args.query) return String(args.query).slice(0, 40)
      if (args.expression) return String(args.expression).slice(0, 40)
      if (args.location) return String(args.location).slice(0, 40)
      if (args.text) return String(args.text).slice(0, 40)
      if (args.action) {
        const bits = [args.action]
        if (args.when) bits.push(args.when)
        return bits.join(' · ').slice(0, 40)
      }
      if (args.value != null && args.from_unit && args.to_unit) {
        return `${args.value} ${args.from_unit}→${args.to_unit}`
      }
      if (args.timezone) return String(args.timezone)
      return ''
    },
    toolStateClass(t) {
      if (t.ok === true || t.phase === 'done') return 'ok'
      if (t.ok === false || t.phase === 'error') return 'fail'
      if (t.phase === 'running') return 'run'
      return 'pending'
    },
    toolStateLabel(t) {
      if (t.ok === true || t.phase === 'done') return '完成'
      if (t.ok === false || t.phase === 'error') return '失敗'
      if (t.phase === 'running') return '執行中…'
      return '等待中'
    },
    toolItemClass(t) {
      return {
        'is-running': t.phase === 'running' || (t.ok == null && t.phase !== 'pending'),
        'is-done': t.ok === true,
        'is-fail': t.ok === false,
      }
    },
    formatToolsUsed(tools) {
      if (!tools?.length) return ''
      return tools
        .map((t) => {
          const state = t.ok === false ? '失敗' : '完成'
          const ms = t.duration_ms != null ? ` ${t.duration_ms}ms` : ''
          const label = t.display_name || this.toolDisplayName(t.name)
          return `${t.icon || this.toolIcon(t.name)} ${label} (${state}${ms})`
        })
        .join('\n')
    },
    /**
     * 從串流緩衝區拆出工具事件 + meta，回傳可見文字
     */
    consumeStreamBuffer(fullText) {
      const lines = fullText.split('\n')
      const visible = []
      let meta = null
      for (const line of lines) {
        if (line.startsWith('__XCG_EVENT__')) {
          try {
            const ev = JSON.parse(line.slice('__XCG_EVENT__'.length))
            if (ev?.type === 'tool_status') {
              this.toolStatusPhase = ev.status || 'running'
              this.toolStatusMessage = ev.message || ''
              if (ev.step != null) this.toolStep = Number(ev.step) || 0
              if (ev.total != null) this.toolTotal = Number(ev.total) || 0
              if (Array.isArray(ev.tools)) {
                // 合併更新，避免閃爍
                this.activeTools = ev.tools.map((t) => ({
                  ...t,
                  icon: t.icon || this.toolIcon(t.name),
                  display_name: t.display_name || this.toolDisplayName(t.name),
                }))
              }
              if (ev.status === 'done' || ev.status === 'skipped') {
                setTimeout(() => {
                  if (this.toolStatusPhase === 'done' || this.toolStatusPhase === 'skipped') {
                    this.toolStatusPhase = ''
                    this.toolStatusMessage = ''
                  }
                }, ev.status === 'skipped' ? 600 : 1800)
              }
            }
          } catch (_) { /* ignore bad event */ }
          continue
        }
        if (line.startsWith('__XCG_META__')) {
          try {
            meta = JSON.parse(line.slice('__XCG_META__'.length))
          } catch (_) {
            meta = null
          }
          continue
        }
        // meta 可能接在同一行尾端（無獨立換行）— 由 extractStreamMeta 處理
        visible.push(line)
      }
      let text = visible.join('\n')
      // 若最後還黏著 meta 前綴
      const extracted = this.extractStreamMeta(text)
      if (extracted.meta) {
        meta = extracted.meta
        text = extracted.text
      }
      return { text, meta }
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
      // 大型 data:image base64 不寫入，避免配額爆掉
      try {
        const toSave = this.messages.slice(-100).map((m) => {
          const copy = { ...m }
          if (
            copy.imageUrl &&
            typeof copy.imageUrl === 'string' &&
            copy.imageUrl.startsWith('data:') &&
            copy.imageUrl.length > 80_000
          ) {
            copy.imageUrl = null
            copy.content =
              (copy.content || '') +
              (copy.content ? '\n' : '') +
              '（圖片預覽過大，未快取到本機）'
          }
          return copy
        })
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
    async sendMessage(options = {}) {
      if (!this.userInput.trim() || this.isLoading || this.isStreaming) return

      // 發送時暫停收音，避免把 AI 朗讀或自己回聲錄進去（略過 onEnd 自動再送）
      this.ignoreNextListenEnd = true
      this.stopListening({ silent: true })
      this.stopTTS()

      // 取消上一次未完成的串流（理論上已阻擋，雙保險）
      if (this.streamAbortController) {
        this.streamAbortController.abort()
      }
      this.streamAbortController = new AbortController()

      this.isLoading = true
      this.isStreaming = false
      this.activeTools = []
      this.toolStatusPhase = ''
      this.toolStatusMessage = ''
      this.toolStep = 0
      this.toolTotal = 0

      const inputMethod = options.inputMethod || this.lastInputMethod || 'text'
      const voiceMode = Boolean(this.carMode || this.autoSpeak || inputMethod === 'voice')
      this.lastInputMethod = 'text'

      this.messages.push({
        type: 'user',
        content: this.userInput,
        timestamp: new Date().toLocaleTimeString('zh-TW'),
        inputMethod,
      })

      const userMessage = this.userInput
      this.userInput = ''
      this.interimTranscript = ''
      this.finalTranscriptBuffer = ''
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
              user_id: this.userId,
              voice_mode: voiceMode,
              car_mode: this.carMode,
              input_method: inputMethod,
              speak_response: this.autoSpeak || this.carMode,
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
          // 即時更新：解析工具事件 + 隱藏 meta
          const live = this.consumeStreamBuffer(fullText)
          // 有工具事件或文字時也算開始回應
          if (!receivedFirstChunk && (live.text || this.toolStatusVisible || this.toolStatusActive)) {
            receivedFirstChunk = true
            this.isStreaming = true
            this.isLoading = false
          }
          this.messages[assistantMsgIndex].content = live.text
          this.scrollToBottom()
        }

        // flush 解碼器殘餘
        const tail = decoder.decode()
        if (tail) {
          fullText += tail
        }

        const { text: cleanText, meta } = this.consumeStreamBuffer(fullText)
        this.messages[assistantMsgIndex].content = cleanText
        this.messages[assistantMsgIndex].streaming = false
        this.toolStatusPhase = ''

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
        if (meta?.tools_used?.length) {
          this.messages[assistantMsgIndex].tools_used = meta.tools_used
          this.activeTools = meta.tools_used
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

        // 🎙️ 自動朗讀 / 車載：說完再開麥
        const shouldSpeak =
          (this.autoSpeak || this.carMode) &&
          cleanText.trim() &&
          !cleanText.startsWith('[ERROR]') &&
          this.messages[assistantMsgIndex].type !== 'system'

        if (shouldSpeak) {
          const speechSrc = meta?.speech_text || cleanText
          await this.speakAssistantText(speechSrc, {
            resumeListen: this.carMode,
          })
        } else if (this.carMode && !this.suppressAutoListen) {
          this.scheduleAutoListen(600)
        }

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
        if (this.carMode && !this.suppressAutoListen) {
          this.scheduleAutoListen(800)
        }
      } finally {
        this.isLoading = false
        this.isStreaming = false
        this.streamAbortController = null
        this.scrollToBottom()
        this.saveMessagesToStorage()
      }
    },

    // ========== 🎙️ 語音輸入 / 輸出 ==========
    initVoice() {
      this.speechRecognitionSupported = isSpeechRecognitionSupported()
      this.speechSynthesisSupported = isSpeechSynthesisSupported()

      const saved = loadVoiceSettings()
      this.autoSpeak = Boolean(saved.autoSpeak)
      this.carMode = Boolean(saved.carMode)
      this.voiceAutoSend = saved.autoSend !== false
      this.voiceLang = saved.lang || 'zh-TW'
      this.voiceRate = Number(saved.rate) || 1.0

      if (this.speechRecognitionSupported) {
        this.setupSpeechRecognizer()
      }
      waitForVoices(2000).catch(() => {})

      if (this.carMode) {
        this.voiceStatusHint = '車載模式已恢復'
        this.reportVoiceEvent('car_mode_on', { restored: true })
        // 不強制立刻開麥，避免未授權時報錯；使用者點一下即可
      }
    },
    setupSpeechRecognizer() {
      if (this.speechRecognizer) {
        this.speechRecognizer.abort()
        this.speechRecognizer = null
      }
      this.speechRecognizer = createSpeechRecognizer({
        lang: this.voiceLang,
        continuous: false,
        interimResults: true,
        onStart: () => {
          this.isListening = true
          this.voiceStatusHint = '正在聽你說話…'
          this.reportVoiceEvent('listen_start')
        },
        onEnd: () => {
          this.isListening = false
          if (this.ignoreNextListenEnd) {
            this.ignoreNextListenEnd = false
            this.finalTranscriptBuffer = ''
            this.interimTranscript = ''
            this.reportVoiceEvent('listen_end', { skipped: true })
            return
          }
          const finalText = (this.finalTranscriptBuffer || '').trim()
          const interim = (this.interimTranscript || '').trim()
          const combined = (finalText || interim).trim()

          if (combined) {
            this.userInput = combined
            this.finalTranscriptBuffer = ''
            this.interimTranscript = ''
            const shouldAutoSend =
              this.voiceAutoSend &&
              (this.carMode || this.lastInputMethod === 'voice')

            if (shouldAutoSend && !this.isLoading && !this.isStreaming) {
              this.lastInputMethod = 'voice'
              this.reportVoiceEvent('auto_send', { transcript: combined.slice(0, 200) })
              this.$nextTick(() => this.sendMessage({ inputMethod: 'voice' }))
              return
            }
          }

          this.voiceStatusHint = this.carMode ? '車載待命' : ''
          this.reportVoiceEvent('listen_end', {
            has_text: Boolean(combined),
          })
        },
        onError: (err, { soft } = {}) => {
          this.isListening = false
          if (soft) {
            this.voiceStatusHint = this.carMode ? '沒聽清楚，可再說一次' : ''
            if (this.carMode && !this.suppressAutoListen && !this.isLoading) {
              this.scheduleAutoListen(900)
            }
            return
          }
          const map = {
            'not-allowed': '麥克風權限被拒，請在瀏覽器允許麥克風',
            'service-not-allowed': '語音服務不可用',
            network: '語音辨識網路錯誤',
            'language-not-supported': '不支援目前語言',
          }
          this.voiceStatusHint = map[err] || `語音錯誤：${err}`
          this.reportVoiceEvent('listen_error', { error: err })
        },
        onResult: ({ interim, final }) => {
          if (interim) this.interimTranscript = interim
          if (final) {
            this.finalTranscriptBuffer = `${this.finalTranscriptBuffer || ''}${final}`.trim()
            this.userInput = this.finalTranscriptBuffer
            this.interimTranscript = ''
          } else if (interim) {
            const base = this.finalTranscriptBuffer || ''
            this.userInput = `${base}${interim}`.trim()
          }
        },
      })
    },
    toggleListening() {
      if (!this.speechRecognitionSupported) {
        this.voiceStatusHint = '請使用 Chrome / Edge 以啟用語音輸入'
        return
      }
      if (this.isListening) {
        this.stopListening()
      } else {
        this.startListening()
      }
    },
    startListening() {
      if (!this.speechRecognizer || this.isLoading || this.isStreaming) return
      this.stopTTS()
      this.suppressAutoListen = false
      this.lastInputMethod = 'voice'
      this.finalTranscriptBuffer = ''
      this.interimTranscript = ''
      // 車載：若輸入框已有未送文字，先清空避免混雜
      if (this.carMode) this.userInput = ''
      this.speechRecognizer.setLang(this.voiceLang)
      const ok = this.speechRecognizer.start()
      if (!ok) {
        this.voiceStatusHint = '無法啟動麥克風，請再試一次'
      }
    },
    stopListening({ silent = false } = {}) {
      if (this.voiceRestartTimer) {
        clearTimeout(this.voiceRestartTimer)
        this.voiceRestartTimer = null
      }
      if (this.speechRecognizer) {
        this.speechRecognizer.stop()
      }
      this.isListening = false
      if (!silent) {
        this.voiceStatusHint = this.carMode ? '已暫停收音' : ''
      }
    },
    scheduleAutoListen(delayMs = 500) {
      if (!this.carMode || !this.speechRecognitionSupported) return
      if (this.suppressAutoListen) return
      if (this.voiceRestartTimer) clearTimeout(this.voiceRestartTimer)
      this.voiceRestartTimer = setTimeout(() => {
        this.voiceRestartTimer = null
        if (
          this.carMode &&
          !this.isLoading &&
          !this.isStreaming &&
          !this.isSpeaking &&
          !this.isListening
        ) {
          this.startListening()
        }
      }, delayMs)
    },
    toggleAutoSpeak() {
      this.autoSpeak = !this.autoSpeak
      if (!this.autoSpeak) this.stopTTS()
      this.persistVoiceSettings()
      this.voiceStatusHint = this.autoSpeak ? '已開啟自動朗讀' : '已關閉自動朗讀'
    },
    toggleCarMode() {
      this.carMode = !this.carMode
      if (this.carMode) {
        this.autoSpeak = true
        this.voiceAutoSend = true
        this.suppressAutoListen = false
        this.voiceStatusHint = '車載模式：點麥克風開始，之後自動聽・說・送'
        this.reportVoiceEvent('car_mode_on')
        this.messages.push({
          type: 'system',
          content:
            '🚗 車載自動語音模式已開啟：回覆會朗讀，朗讀結束後自動開麥，說完自動送出。請注意行車安全。',
          timestamp: new Date().toLocaleTimeString('zh-TW'),
        })
        this.scrollToBottom()
      } else {
        this.suppressAutoListen = true
        this.stopListening({ silent: true })
        this.stopTTS()
        this.voiceStatusHint = '車載模式已關閉'
        this.reportVoiceEvent('car_mode_off')
      }
      this.persistVoiceSettings()
    },
    persistVoiceSettings() {
      saveVoiceSettings({
        lang: this.voiceLang,
        rate: this.voiceRate,
        autoSpeak: this.autoSpeak,
        carMode: this.carMode,
        autoSend: this.voiceAutoSend,
      })
      // 同步後端（失敗略過）
      this.syncVoiceSettingsToBackend()
    },
    async syncVoiceSettingsToBackend() {
      try {
        const headers = await this.buildRequestHeaders()
        await axios.put(
          `${API_URL}/api/voice/settings`,
          {
            user_id: this.userId,
            settings: {
              lang: this.voiceLang,
              rate: this.voiceRate,
              auto_speak: this.autoSpeak,
              car_mode: this.carMode,
              auto_send: this.voiceAutoSend,
              continuous: false,
              strip_emojis_for_speech: true,
            },
          },
          { headers }
        )
      } catch (e) {
        console.warn('[voice] 同步設定到後端失敗:', e?.message || e)
      }
    },
    async reportVoiceEvent(eventType, detail = {}) {
      try {
        const headers = await this.buildRequestHeaders()
        await fetch(VOICE_EVENTS_API, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            user_id: this.userId,
            conversation_id: this.conversationId,
            event_type: eventType,
            detail,
            transcript: detail.transcript || null,
          }),
        })
      } catch (_) {
        /* 非關鍵 */
      }
    },
    async prepareSpeechOnServer(text) {
      try {
        const headers = await this.buildRequestHeaders()
        const { data } = await axios.post(
          VOICE_PREPARE_SPEECH_API,
          { text, strip_emojis: true, max_chars: 800 },
          { headers }
        )
        return data?.speech_text || sanitizeForSpeech(text)
      } catch {
        return sanitizeForSpeech(text)
      }
    },
    async speakAssistantText(text, { resumeListen = false } = {}) {
      if (!this.speechSynthesisSupported || !text) return
      try {
        this.isSpeaking = true
        this.voiceStatusHint = '正在朗讀回覆…'
        this.reportVoiceEvent('speak_start')
        const speech = await this.prepareSpeechOnServer(text)
        await speakText(speech, {
          lang: this.voiceLang,
          rate: this.carMode ? Math.min(1.15, this.voiceRate + 0.05) : this.voiceRate,
          stripEmojis: true,
        })
        this.reportVoiceEvent('speak_end')
      } catch (e) {
        console.warn('[voice] TTS 失敗:', e?.message || e)
        this.voiceStatusHint = '朗讀失敗'
      } finally {
        this.isSpeaking = false
        this.voiceStatusHint = this.carMode ? '車載待命' : ''
        if (resumeListen && this.carMode && !this.suppressAutoListen) {
          this.scheduleAutoListen(400)
        }
      }
    },
    async speakLastAssistant() {
      const last = [...this.messages]
        .reverse()
        .find((m) => m.type === 'assistant' && m.content && !m.streaming)
      if (!last) {
        this.voiceStatusHint = '沒有可朗讀的回覆'
        return
      }
      if (this.isSpeaking) {
        this.stopTTS()
        return
      }
      await this.speakAssistantText(last.content, { resumeListen: this.carMode })
    },
    stopTTS() {
      stopSpeaking()
      this.isSpeaking = false
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
    isImageFile(file) {
      if (!file) return false
      if (file.type && file.type.startsWith('image/')) return true
      return /\.(png|jpe?g|webp|gif)$/i.test(file.name || '')
    },
    openImagePreview(url) {
      if (url) this.imagePreviewUrl = url
    },
    extractUploadError(error) {
      const d = error.response?.data?.detail
      if (!d) return error.message
      if (typeof d === 'string') return d
      if (d.message) return d.message
      try {
        return JSON.stringify(d)
      } catch {
        return error.message
      }
    },
    async uploadOneFile(file, { visionPrompt } = {}) {
      const localPreview = this.isImageFile(file) ? URL.createObjectURL(file) : null
      const statusIdx = this.messages.length
      this.messages.push({
        type: 'system',
        content: this.isImageFile(file)
          ? `⏳ 正在上傳並理解圖片「${file.name}」…`
          : `⏳ 正在上傳檔案「${file.name}」…`,
        timestamp: new Date().toLocaleTimeString('zh-TW'),
        imageUrl: localPreview || undefined,
        imageName: this.isImageFile(file) ? file.name : undefined,
      })
      this.scrollToBottom()

      try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('conversation_id', this.conversationId)
        formData.append('user_id', this.userId)
        if (visionPrompt) {
          formData.append('prompt', visionPrompt)
        }

        const headers = await this.buildRequestHeaders()
        // FormData 勿強制 Content-Type，讓瀏覽器帶 boundary
        delete headers['Content-Type']

        const response = await axios.post(`${API_URL}/api/upload_file`, formData, {
          headers,
        })
        const data = response.data || {}
        const isImage = data.is_image || this.isImageFile(file)
        const imageUrl =
          data.preview_data_url || data.file_url || localPreview || null
        const summary = data.summary || '檔案已上傳'
        const fileType = data.file_type || ''
        const parsed = data.parsed ? '✅ 已解析' : '⚠️ 未解析'
        const visionLine = data.vision_analysis
          ? `\n🔍 Vision：${String(data.vision_analysis).slice(0, 120)}${data.vision_analysis.length > 120 ? '…' : ''}`
          : ''

        // 更新上傳狀態訊息為成功 + 圖片預覽
        this.messages[statusIdx] = {
          type: isImage ? 'user' : 'system',
          content: isImage
            ? `已上傳圖片，等待小宸光解讀…`
            : `📎 檔案上傳成功\n📄 ${file.name} (${fileType})\n${parsed}\n📝 ${summary}${visionLine}`,
          timestamp: new Date().toLocaleTimeString('zh-TW'),
          imageUrl: isImage ? imageUrl : undefined,
          imageName: isImage ? file.name : undefined,
          visionModel: data.vision_model,
        }

        if (data.ai_analysis) {
          this.messages.push({
            type: 'assistant',
            content: data.ai_analysis,
            timestamp: new Date().toLocaleTimeString('zh-TW'),
            usage: data.usage
              ? {
                  prompt_tokens: data.usage.prompt_tokens,
                  completion_tokens: data.usage.completion_tokens,
                  total_tokens: data.usage.total_tokens,
                  cost_usd: null,
                  model: data.vision_model,
                }
              : undefined,
          })
        }

        if (data.usage) {
          this.applyUsagePayload({
            ...data.usage,
            model: data.vision_model,
            cost_usd: data.usage.cost_usd,
          })
        }

        this.scrollToBottom()
        this.saveMessagesToStorage()
      } catch (error) {
        const msg = this.extractUploadError(error)
        this.messages[statusIdx] = {
          type: 'system',
          content: `❌ 「${file.name}」上傳/分析失敗：${msg}`,
          timestamp: new Date().toLocaleTimeString('zh-TW'),
          imageUrl: localPreview || undefined,
          imageName: this.isImageFile(file) ? file.name : undefined,
        }
        this.scrollToBottom()
      } finally {
        // object URL 若已被 data_url 取代可不 revoke；為避免破圖延後 revoke
        if (localPreview) {
          setTimeout(() => {
            try {
              URL.revokeObjectURL(localPreview)
            } catch (_) { /* ignore */ }
          }, 60_000)
        }
      }
    },
    async handleFileUpload(event) {
      const files = Array.from(event.target.files || [])
      if (!files.length) return
      for (const file of files) {
        await this.uploadOneFile(file)
      }
      event.target.value = ''
    },
    async handleImageUpload(event) {
      const files = Array.from(event.target.files || [])
      if (!files.length) return
      this.isUploadingImage = true
      try {
        for (const file of files) {
          if (!this.isImageFile(file)) {
            this.messages.push({
              type: 'system',
              content: `⚠️ 「${file.name}」不是支援的圖片格式`,
              timestamp: new Date().toLocaleTimeString('zh-TW'),
            })
            continue
          }
          await this.uploadOneFile(file, {
            visionPrompt:
              '請用繁體中文詳細描述這張圖片，包含場景、物體、文字（OCR）與氛圍，不超過 300 字。',
          })
        }
      } finally {
        this.isUploadingImage = false
        event.target.value = ''
      }
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
    },
    onLoadHistoryConversation({ conversationId, messages }) {
      if (!conversationId) return
      this.conversationId = conversationId
      localStorage.setItem('xiaochenguang_conversation_id', conversationId)
      const mapped = (messages || []).map((m) => ({
        type: m.type === 'user' ? 'user' : m.type === 'assistant' ? 'assistant' : 'system',
        content: m.content || '',
        timestamp: m.timestamp || new Date().toLocaleTimeString('zh-TW'),
        streaming: false,
      }))
      this.messages =
        mapped.length > 0
          ? mapped
          : [
              {
                type: 'system',
                content: '已載入歷史對話（無訊息內容）',
                timestamp: new Date().toLocaleTimeString('zh-TW'),
              },
            ]
      this.messages.push({
        type: 'system',
        content: `📚 已從歷史載入對話 ${conversationId.slice(0, 12)}…，可繼續聊天`,
        timestamp: new Date().toLocaleTimeString('zh-TW'),
      })
      this.saveMessagesToStorage()
      this.loadMemories()
      this.$nextTick(() => this.scrollToBottom())
    },
    onHistoryConversationDeleted(deletedId) {
      if (deletedId && deletedId === this.conversationId) {
        localStorage.removeItem('xiaochenguang_messages')
        localStorage.removeItem('xiaochenguang_conversation_id')
        this.messages = [
          {
            type: 'system',
            content: '🗑️ 目前對話已從歷史刪除，已為你開啟新對話',
            timestamp: new Date().toLocaleTimeString('zh-TW'),
          },
        ]
        this.conversationId = this.getOrCreateConversationId()
        this.saveMessagesToStorage()
      }
      this.loadMemories()
    },
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
    // 🎙️ 語音初始化
    this.initVoice()
    // 路由 /history 時自動打開歷史面板
    if (this.$route?.meta?.openHistory || this.$route?.path === '/history') {
      this.showHistoryPanel = true
    }
    this.$nextTick(() => this.scrollToBottom())
    window.addEventListener('beforeunload', this.handleBeforeUnload)
  },

  beforeUnmount() {
    window.removeEventListener('beforeunload', this.handleBeforeUnload)
    if (typeof this.authUnsubscribe === 'function') {
      this.authUnsubscribe()
    }
    this.suppressAutoListen = true
    this.stopListening({ silent: true })
    this.stopTTS()
    if (this.voiceRestartTimer) {
      clearTimeout(this.voiceRestartTimer)
      this.voiceRestartTimer = null
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

.tools-tag {
  font-size: 0.7rem;
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
}

.message-assistant .usage-tag {
  color: #5b21b6;
}

.tool-status-bubble {
  background: linear-gradient(135deg, #ecfdf5 0%, #e0e7ff 100%) !important;
  border: 1px solid #a7f3d0 !important;
  color: #065f46 !important;
  text-align: left !important;
  max-width: 92% !important;
}

.tool-status-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.45rem;
}

.tool-status-titles {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  flex: 1;
  min-width: 0;
  text-align: left;
}

.tool-status-msg {
  font-size: 0.78rem;
  font-weight: 500;
  opacity: 0.85;
  color: #374151;
}

.tool-progress-chip {
  font-size: 0.75rem;
  font-weight: 700;
  background: rgba(67, 56, 202, 0.12);
  color: #4338ca;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  flex-shrink: 0;
}

.tool-progress-bar {
  height: 4px;
  background: rgba(99, 102, 241, 0.15);
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 0.55rem;
}

.tool-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 999px;
  transition: width 0.25s ease;
}

.tool-spin {
  display: inline-block;
  animation: toolPulse 1s ease-in-out infinite;
}

@keyframes toolPulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.15); opacity: 0.75; }
}

.tool-status-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.tool-status-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  padding: 0.35rem 0.45rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.55);
}

.tool-status-item.is-running {
  background: rgba(254, 243, 199, 0.7);
}

.tool-status-item.is-done {
  background: rgba(209, 250, 229, 0.55);
}

.tool-status-item.is-fail {
  background: rgba(254, 226, 226, 0.7);
}

.tool-icon {
  font-size: 1rem;
}

.tool-name {
  font-weight: 700;
}

.tool-args {
  color: #4b5563;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-state {
  margin-left: auto;
  font-size: 0.75rem;
  padding: 0.05rem 0.4rem;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
}

.tool-state.ok {
  background: #d1fae5;
  color: #047857;
}

.tool-state.fail {
  background: #fee2e2;
  color: #b91c1c;
}

.tool-state.run {
  background: #fef3c7;
  color: #b45309;
}

.tool-state.pending {
  background: #e5e7eb;
  color: #4b5563;
}

.tool-errors {
  margin-top: 0.45rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.tool-error-line {
  font-size: 0.78rem;
  color: #b91c1c;
  text-align: left;
}

.phase-error {
  border-color: #fecaca !important;
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%) !important;
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

.message-image-wrap {
  margin-bottom: 0.6rem;
}

.message-image {
  display: block;
  max-width: min(320px, 70vw);
  max-height: 240px;
  border-radius: 12px;
  object-fit: cover;
  cursor: zoom-in;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.message-user .message-image {
  margin-left: auto;
}

.image-caption {
  margin-top: 0.35rem;
  font-size: 0.75rem;
  opacity: 0.85;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}

.vision-badge {
  background: rgba(99, 102, 241, 0.15);
  color: #4338ca;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
}

.message-user .vision-badge {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.vision-btn {
  background: linear-gradient(135deg, #a78bfa 0%, #6366f1 100%) !important;
  color: white !important;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.75);
  z-index: 2000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  gap: 0.75rem;
}

.image-preview-full {
  max-width: min(960px, 95vw);
  max-height: 80vh;
  border-radius: 12px;
  object-fit: contain;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
}

.image-preview-close {
  border: none;
  border-radius: 999px;
  padding: 0.5rem 1.2rem;
  background: white;
  color: #111827;
  font-weight: 700;
  cursor: pointer;
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

.voice-speak-btn {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
}

.voice-speak-btn.active {
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.35);
  outline: 2px solid #22d3ee;
}

.car-mode-btn {
  background: linear-gradient(135deg, #0f766e 0%, #115e59 100%);
}

.car-mode-btn.active {
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.4);
  outline: 2px solid #34d399;
  animation: car-glow 1.8s ease-in-out infinite;
}

@keyframes car-glow {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.12); }
}

/* 語音狀態列 */
.voice-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin: 0 1.5rem 0.5rem;
  padding: 0.55rem 0.9rem;
  border-radius: 12px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  color: #0c4a6e;
  font-size: 0.88rem;
  flex-wrap: wrap;
}

.voice-bar.listening {
  background: #fef2f2;
  border-color: #fecaca;
  color: #991b1b;
}

.voice-bar.speaking {
  background: #ecfeff;
  border-color: #a5f3fc;
  color: #155e75;
}

.voice-bar.car {
  background: linear-gradient(90deg, #042f2e 0%, #134e4a 100%);
  border-color: #14b8a6;
  color: #ecfdf5;
  font-size: 1rem;
  padding: 0.75rem 1rem;
}

.voice-bar.unsupported {
  background: #f9fafb;
  border-color: #e5e7eb;
  color: #6b7280;
}

.voice-bar-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.voice-bar-right {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.voice-pulse {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6);
  animation: pulse-mic 1.2s infinite;
}

@keyframes pulse-mic {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.55); }
  70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

.voice-interim {
  opacity: 0.85;
  font-style: italic;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.voice-mini-btn {
  border: none;
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
}

.voice-bar.car .voice-mini-btn {
  background: #14b8a6;
  color: white;
}

.voice-mini-btn.danger {
  background: #ef4444;
  color: white;
}

.voice-warn {
  font-size: 0.78rem;
  opacity: 0.9;
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

.input-wrapper.car-input {
  padding: 1.1rem 1.25rem;
  background: #f0fdfa;
  border-top: 2px solid #14b8a6;
}

.mic-button {
  flex-shrink: 0;
  min-width: 4.2rem;
  padding: 0.7rem 0.65rem;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, #f43f5e 0%, #e11d48 100%);
  color: white;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  box-shadow: 0 4px 12px rgba(244, 63, 94, 0.35);
  transition: transform 0.15s, box-shadow 0.15s;
}

.mic-button:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.03);
}

.mic-button.listening {
  background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
  animation: pulse-mic-btn 1s ease-in-out infinite;
}

.mic-button.car {
  min-width: 5rem;
  min-height: 3.6rem;
  font-size: 1.05rem;
  border-radius: 18px;
}

.mic-button:disabled,
.mic-button.disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

@keyframes pulse-mic-btn {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.mic-icon {
  font-size: 1.25rem;
  line-height: 1;
}

.mic-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.tts-button {
  flex-shrink: 0;
  width: 2.75rem;
  height: 2.75rem;
  border: 2px solid #e5e7eb;
  border-radius: 14px;
  background: #f8fafc;
  cursor: pointer;
  font-size: 1.15rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tts-button.active {
  border-color: #06b6d4;
  background: #ecfeff;
}

.tts-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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

.input-wrapper.car-input .message-input {
  font-size: 1.1rem;
  padding: 1rem 1.25rem;
  min-height: 3.2rem;
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
