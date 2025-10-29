<template>
  <div class="chat-interface">
    <div class="chat-container">
      <div class="messages-area" ref="messagesArea">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.type]">
          <div class="message-content">
            <p>{{ msg.content }}</p>
            <span v-if="msg.emotion" class="emotion-tag">
              {{ getEmotionEmoji(msg.emotion.dominant_emotion) }} {{ msg.emotion.dominant_emotion }}
            </span>
          </div>
          <small class="timestamp">{{ msg.timestamp }}</small>
        </div>
        <div v-if="isLoading" class="message assistant">
          <div class="message-content">
            <p class="loading">小宸光正在思考...</p>
          </div>
        </div>
      </div>

      <div class="input-section">
        <input
          v-model="userInput"
          @keyup.enter="sendMessage"
          placeholder="輸入您的訊息..."
          class="message-input"
          :disabled="isLoading"
        />
        <button @click="sendMessage" :disabled="isLoading" class="send-btn">
          {{ isLoading ? '發送中...' : '發送' }}
        </button>
      </div>

      <div class="action-buttons">
        <label class="upload-btn">
          📎 上傳檔案
          <input type="file" @change="handleFileUpload" style="display: none" />
        </label>
        <button @click="goToHealthCheck" class="health-check-btn">📋 健康檢查</button>
      </div>
    </div>

    <div class="sidebar">
      <!-- ✨ 新增：Reflection 反思區塊（右側顯示） -->
      <div class="reflections-section">
        <h3>💭 反思</h3>
        <div v-if="latestReflection" class="reflection-display">
          <div v-if="latestReflection.summary" class="reflection-summary">
            {{ latestReflection.summary }}
          </div>
          <div v-if="latestReflection.causes && latestReflection.causes.length > 0" class="reflection-causes">
            <div class="causes-title">🔍 原因分析</div>
            <div v-for="(cause, idx) in latestReflection.causes" :key="idx" class="cause-item">
              {{ cause }}
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          暫無反思數據
        </div>
      </div>
      
      <div class="memories-section">
        <h3>💭 記憶列表</h3>
        <div v-if="memories.length > 0" class="memories-list">
          <div v-for="(memory, index) in memories" :key="index" class="memory-item">
            {{ memory.content || memory }}
          </div>
        </div>
        <div v-else class="empty-state">
          暫無記憶
        </div>
      </div>

      <div class="emotions-section">
        <h3>😊 情緒狀態</h3>
        <div v-if="emotionalStates.length > 0" class="emotions-list">
          <div v-for="(state, index) in emotionalStates" :key="index" class="emotion-item">
            {{ getEmotionEmoji(state.emotion || state) }} {{ state.emotion || state }}
          </div>
        </div>
        <div v-else class="empty-state">
          暫無情緒數據
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { CHAT_API } from '../config.js';

const getApiUrl = () => {
  const url = import.meta.env.VITE_API_URL
  console.log('🔗 [ChatInterface] API URL 環境變數:', url)
  
  if (!url || url === 'undefined' || url === 'null') {
    console.warn('⚠️ [ChatInterface] VITE_API_URL 未定義，使用預設 URL')
    return 'https://setup-the-bot-to-railway-production.up.railway.app'
  }
  
  return url
}

const API_URL = getApiUrl()
console.log('🚀 [ChatInterface] 最終 API_URL:', API_URL)

export default {
  name: 'ChatInterface',
  data() {
    return {
      messages: [],
      userInput: '',
      isLoading: false,
      memories: [],
      emotionalStates: [],
      latestReflection: null,
      conversationId: this.generateConversationId(),
      userId: 'user_' + Date.now()
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
        console.log('📤 [ChatInterface] 發送訊息...')
        console.log('[📍 ChatInterface] API 端點:', CHAT_API)
        console.log('📋 [ChatInterface] 請求數據:', {
          user_message: userMessage,
          conversation_id: this.conversationId,
          user_id: this.userId
        })
        
        const response = await axios.post(CHAT_API, {
          user_message: userMessage,
          conversation_id: this.conversationId,
          user_id: this.userId
        })
        
        console.log('✅ [ChatInterface] 收到回應:', response.data)
        
        // ✨ 添加 AI 回應
        this.messages.push({
          type: 'assistant',
          content: response.data.assistant_message,
          emotion: response.data.emotion_analysis,
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
        
        // ✨ 更新右側 Reflection 區塊
        if (response.data.reflection) {
          this.latestReflection = response.data.reflection
          console.log('💭 [ChatInterface] 更新 Reflection:', this.latestReflection)
        }
        
        this.loadMemories()
        this.loadEmotionalStates()
      } catch (error) {
        console.error('❌ [ChatInterface] 發送訊息錯誤:', {
          message: error.message,
          status: error.response?.status,
          statusText: error.response?.statusText,
          url: error.config?.url,
          data: error.response?.data,
          apiUrl: API_URL
        })
        
        let errorMessage = '抱歉，發生錯誤了 😢'
        if (error.response?.status === 405) {
          errorMessage = '❌ 方法不被允許 (405) - 檢查後端路由配置'
        } else if (error.response?.status === 404) {
          errorMessage = '❌ 未找到端點 (404) - 檢查 API URL'
        } else if (error.response?.status === 500) {
          errorMessage = '❌ 伺服器錯誤 (500) - 檢查後端日誌'
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
        console.log('📚 [ChatInterface] 正在載入記憶...')
        const url = `${API_URL}/api/memories/${this.conversationId}?limit=10`
        console.log('📍 [ChatInterface] 記憶端點:', url)
        const response = await axios.get(url)
        this.memories = response.data
        console.log('✅ [ChatInterface] 記憶載入成功:', this.memories.length, '條')
      } catch (error) {
        console.error('❌ [ChatInterface] 載入記憶錯誤:', {
          message: error.message,
          status: error.response?.status
        })
        this.memories = []
      }
    },
    async loadEmotionalStates() {
      try {
        console.log('😊 [ChatInterface] 正在載入情緒狀態...')
        const url = `${API_URL}/api/emotional-states/${this.userId}?limit=10`
        const response = await axios.get(url)
        this.emotionalStates = response.data
        console.log('✅ [ChatInterface] 情緒狀態載入成功:', this.emotionalStates.length, '條')
      } catch (error) {
        console.warn('⚠️ [ChatInterface] 載入情緒狀態錯誤:', error.message)
        this.emotionalStates = []
      }
    },
    async handleFileUpload(event) {
      const file = event.target.files[0]
      if (!file) return
      
      try {
        console.log('📤 [ChatInterface] 正在上傳檔案:', file.name)
        const formData = new FormData()
        formData.append('file', file)
        formData.append('conversation_id', this.conversationId)
        
        const response = await axios.post(`${API_URL}/api/upload`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        })
        
        console.log('✅ [ChatInterface] 檔案上傳成功:', response.data)
        this.messages.push({
          type: 'system',
          content: `📎 檔案 "${file.name}" 已上傳`,
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
      } catch (error) {
        console.error('❌ [ChatInterface] 檔案上傳錯誤:', error.message)
        this.messages.push({
          type: 'system',
          content: '❌ 檔案上傳失敗，請重試',
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
      }
    },
    goToHealthCheck() {
      console.log('📋 [ChatInterface] 開啟健康檢查頁面')
      window.open('/status', '_blank')
    }
  },
  mounted() {
    console.log('📌 [ChatInterface] 組件已掛載，開始載入數據')
    console.log('👤 User ID:', this.userId)
    console.log('💬 Conversation ID:', this.conversationId)
    this.loadMemories()
    this.loadEmotionalStates()
  }
}
</script>

<style scoped>
.chat-interface {
  display: flex;
  height: 100vh;
  background-color: #f5f5f5;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: white;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message {
  display: flex;
  flex-direction: column;
  gap: 5px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  align-self: flex-end;
}

.message.user .message-content {
  background-color: #4CAF50;
  color: white;
  padding: 10px 15px;
  border-radius: 15px;
  max-width: 70%;
}

.message.assistant {
  align-self: flex-start;
}

.message.assistant .message-content {
  background-color: #e0e0e0;
  color: black;
  padding: 10px 15px;
  border-radius: 15px;
  max-width: 70%;
}

.message.system {
  align-self: center;
}

.message.system .message-content {
  background-color: #fff9c4;
  color: #f57f17;
  padding: 10px 15px;
  border-radius: 15px;
  max-width: 90%;
  text-align: center;
}

.message-content p {
  margin: 0;
  word-wrap: break-word;
}

.emotion-tag {
  font-size: 0.8em;
  margin-top: 5px;
  opacity: 0.8;
}

/* ✨ 新增：Reflection 反思區塊樣式 */
.reflection-block {
  margin-top: 8px;
  padding: 10px 12px;
  background-color: #f0f7ff;
  border-left: 3px solid #2196F3;
  border-radius: 8px;
  font-size: 0.9em;
  max-width: 70%;
}

.reflection-header {
  font-weight: bold;
  color: #1976D2;
  margin-bottom: 6px;
  font-size: 0.95em;
}

.reflection-summary {
  color: #424242;
  margin-bottom: 8px;
  line-height: 1.4;
}

.reflection-causes {
  margin-top: 8px;
}

.causes-title {
  font-weight: 600;
  color: #1976D2;
  margin-bottom: 4px;
  font-size: 0.9em;
}

.cause-item {
  padding: 4px 0;
  color: #616161;
  font-size: 0.85em;
  line-height: 1.3;
}

.timestamp {
  font-size: 0.75em;
  opacity: 0.6;
  margin-top: 2px;
}

.loading {
  animation: blink 1.5s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.input-section {
  display: flex;
  gap: 10px;
  padding: 15px 20px;
  border-top: 1px solid #ddd;
}

.message-input {
  flex: 1;
  padding: 10px 15px;
  border: 1px solid #ddd;
  border-radius: 20px;
  font-size: 1em;
  outline: none;
}

.message-input:focus {
  border-color: #4CAF50;
  box-shadow: 0 0 5px rgba(76, 175, 80, 0.3);
}

.send-btn {
  padding: 10px 30px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 1em;
  transition: background-color 0.3s;
}

.send-btn:hover:not(:disabled) {
  background-color: #45a049;
}

.send-btn:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.action-buttons {
  display: flex;
  gap: 10px;
  padding: 10px 20px;
  border-top: 1px solid #ddd;
}

.upload-btn,
.health-check-btn {
  padding: 8px 15px;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 15px;
  cursor: pointer;
  font-size: 0.9em;
  transition: background-color 0.3s;
}

.upload-btn:hover,
.health-check-btn:hover {
  background-color: #0b7dda;
}

.sidebar {
  width: 250px;
  background-color: #fafafa;
  border-left: 1px solid #ddd;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
  overflow-y: auto;
}

.memories-section,
.emotions-section,
.reflections-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.memories-section h3,
.emotions-section h3,
.reflections-section h3 {
  margin: 0;
  font-size: 1em;
  color: #333;
}

.memories-list,
.emotions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.memory-item,
.emotion-item {
  padding: 8px 12px;
  background-color: white;
  border-radius: 8px;
  font-size: 0.9em;
  border-left: 3px solid #4CAF50;
  word-wrap: break-word;
}

.emotion-item {
  border-left-color: #FF9800;
}

/* ✨ Reflection 反思區塊樣式 */
.reflection-display {
  padding: 12px;
  background-color: #f0f7ff;
  border-left: 3px solid #2196F3;
  border-radius: 8px;
  font-size: 0.9em;
}

.reflection-summary {
  color: #424242;
  margin-bottom: 10px;
  line-height: 1.4;
  font-weight: 500;
}

.reflection-causes {
  margin-top: 10px;
}

.causes-title {
  font-weight: 600;
  color: #1976D2;
  margin-bottom: 6px;
  font-size: 0.9em;
}

.cause-item {
  padding: 4px 0;
  color: #616161;
  font-size: 0.85em;
  line-height: 1.4;
  padding-left: 12px;
  position: relative;
}

.cause-item::before {
  content: "•";
  position: absolute;
  left: 0;
  color: #2196F3;
}

.empty-state {
  color: #999;
  font-size: 0.9em;
  text-align: center;
  padding: 20px 10px;
}

/* 響應式設計 */
@media (max-width: 768px) {
  .chat-interface {
    flex-direction: column;
  }
  
  .sidebar {
    width: 100%;
    border-left: none;
    border-top: 1px solid #ddd;
    flex-direction: row;
    max-height: 150px;
  }
  
  .memories-section,
  .emotions-section,
  .reflections-section {
    flex: 1;
  }
}
</style>
