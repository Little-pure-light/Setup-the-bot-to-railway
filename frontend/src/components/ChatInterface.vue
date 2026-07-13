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
        <button @click="goToHealthCheck" class="status-btn">
          📋 系統狀態
        </button>
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
                <p class="message-text">{{ msg.content }}</p>
                <div class="message-footer">
                  <span v-if="msg.emotion" class="emotion-tag">
                    {{ getEmotionEmoji(msg.emotion.dominant_emotion) }}
                    {{ msg.emotion.dominant_emotion }}
                  </span>
                  <small class="timestamp">{{ msg.timestamp }}</small>
                </div>
              </div>
            </div>
            
            <!-- Loading 狀態 -->
            <div v-if="isLoading" class="message-wrapper message-assistant">
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
  </div>
</template>

<script>
import axios from 'axios'
import { CHAT_API } from '../config.js'
import CopilotWindow from './CopilotWindow.vue'

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
    CopilotWindow
  },
  data() {
    return {
      messages: [],
      userInput: '',
      isLoading: false,
      memories: [],
      emotionalStates: [],
      latestReflection: null,
      conversationId: this.generateConversationId(),
      userId: 'user_' + Date.now(),
      copilotWindowVisible: false
    }
  },
  methods: {
    generateConversationId() {
      return 'conv_' + Date.now() + '_' + Math.random().toString(36).substring(7)
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
      if (!this.userInput.trim()) return
      
      this.isLoading = true
      
      this.messages.push({
        type: 'user',
        content: this.userInput,
        timestamp: new Date().toLocaleTimeString('zh-TW')
      })
      
      const userMessage = this.userInput
      this.userInput = ''
      this.scrollToBottom()
      
      try {
        const response = await axios.post(CHAT_API, {
          user_message: userMessage,
          conversation_id: this.conversationId,
          user_id: this.userId
        })
        
        this.messages.push({
          type: 'assistant',
          content: response.data.assistant_message,
          emotion: response.data.emotion_analysis,
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
        
        if (response.data.reflection) {
          this.latestReflection = response.data.reflection
        }
        
        this.loadMemories()
        this.loadEmotionalStates()
      } catch (error) {
        let errorMessage = '抱歉，發生錯誤了 😢'
        if (error.response?.status === 405) {
          errorMessage = '❌ 方法不被允許 (405)'
        } else if (error.response?.status === 404) {
          errorMessage = '❌ 未找到端點 (404)'
        } else if (error.response?.status === 500) {
          errorMessage = '❌ 伺服器錯誤 (500)'
        }
        
        this.messages.push({
          type: 'system',
          content: errorMessage,
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
      } finally {
        this.isLoading = false
        this.scrollToBottom()
      }
    },
    async loadMemories() {
      try {
        const response = await axios.get(`${API_URL}/api/memories/${this.conversationId}?limit=10`)
        this.memories = response.data
      } catch (error) {
        this.memories = []
      }
    },
    async loadEmotionalStates() {
      try {
        const response = await axios.get(`${API_URL}/api/emotional-states/${this.userId}?limit=10`)
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
      if (!confirm('確定要結束並封存此對話嗎？對話將被上傳到 IPFS 永久保存。')) {
        return
      }
      
      try {
        this.messages.push({
          type: 'system',
          content: '⏳ 正在封存對話到 IPFS...',
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
        this.scrollToBottom()
        
        const response = await axios.post(`${API_URL}/api/archive_conversation`, {
          conversation_id: this.conversationId,
          user_id: this.userId,
          include_attachments: true
        })
        
        const cid = response.data.ipfs_cid
        const gatewayUrl = response.data.gateway_url
        
        this.messages.push({
          type: 'system',
          content: `✅ 對話已封存到 IPFS\n🔗 CID: ${cid}\n🌐 查看: ${gatewayUrl}`,
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
        this.scrollToBottom()
        
        alert(`對話已成功封存！\n\nIPFS CID: ${cid}\n\n你可以通過以下網址查看:\n${gatewayUrl}`)
        
      } catch (error) {
        this.messages.push({
          type: 'system',
          content: `❌ 封存失敗: ${error.response?.data?.detail || error.message}`,
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
  mounted() {
    this.loadMemories()
    this.loadEmotionalStates()
    window.addEventListener('beforeunload', this.handleBeforeUnload)
  },
  beforeUnmount() {
    window.removeEventListener('beforeunload', this.handleBeforeUnload)
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

.status-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
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
