```vue
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

      <div class="input-area">
        <input 
          v-model="userInput" 
          @keyup.enter="sendMessage"
          placeholder="輸入訊息與小宸光對話..."
          :disabled="isLoading"
        />
        <button @click="sendMessage" :disabled="isLoading || !userInput.trim()">
          發送
        </button>
      </div>

      <div class="file-upload-area">
        <input 
          type="file" 
          ref="fileInput" 
          @change="handleFileUpload" 
          accept="image/*,application/pdf"
          style="display: none"
        />
        <button @click="$refs.fileInput.click()" :disabled="isLoading">
          📎 上傳檔案
        </button>
        <button @click="goToHealthCheck" :disabled="isLoading">
          📋 健康檢查
        </button>
        <span v-if="uploadedFile" class="file-name">{{ uploadedFile }}</span>
      </div>
    </div>

    <div class="sidebar">
      <h3>💭 記憶列表</h3>
      <div class="memories-list">
        <div v-for="memory in memories" :key="memory.id" class="memory-item">
          <p><strong>你:</strong> {{ memory.user_message }}</p>
          <p><strong>小宸光:</strong> {{ memory.assistant_mes }}</p>
          <small>{{ formatDate(memory.created_at) }}</small>
        </div>
      </div>

      <h3>😊 情緒狀態</h3>
      <div class="emotion-chart">
        <div v-for="emotion in emotionalStates" :key="emotion.id" class="emotion-item">
          <span>{{ getEmotionEmoji(emotion.emotion_type) }}</span>
          <span>{{ emotion.emotion_type }}</span>
          <div class="intensity-bar">
            <div class="intensity-fill" :style="{ width: (emotion.intensity * 100) + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
const API_URL = import.meta.env.VITE_API_URL

export default {
  name: 'ChatInterface',
  data() {
    return {
      messages: [],
      userInput: '',
      isLoading: false,
      conversationId: this.generateConversationId(),
      userId: 'user_' + Date.now(),
      memories: [],
      emotionalStates: [],
      uploadedFile: null
    }
  },
  mounted() {
    this.loadMemories()
    this.loadEmotionalStates()
  },
  methods: {
    generateConversationId() {
      return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
    },
    async sendMessage() {
      if (!this.userInput.trim()) return

      const userMessage = this.userInput.trim()
      this.messages.push({
        type: 'user',
        content: userMessage,
        timestamp: new Date().toLocaleTimeString('zh-TW')
      })

      this.userInput = ''
      this.isLoading = true
      this.scrollToBottom()

      try {
        const response = await axios.post(`${API_URL}/api/chat`, {
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

        this.loadMemories()
        this.loadEmotionalStates()
      } catch (error) {
        console.error('發送訊息錯誤:', error)
        this.messages.push({
          type: 'system',
          content: '抱歉，發生錯誤了 😢',
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
        console.error('載入記憶錯誤:', error)
      }
    },
    async loadEmotionalStates() {
      try {
        const response = await axios.get(`${API_URL}/api/emotional-states/${this.userId}?limit=10`)
        this.emotionalStates = response.data
      } catch (error) {
        console.error('載入情緒狀態錯誤:', error)
      }
    },
    async handleFileUpload(event) {
      const file = event.target.files[0]
      if (!file) return

      const formData = new FormData()
      formData.append('file', file)
      formData.append('conversation_id', this.conversationId)

      this.isLoading = true

      try {
        const response = await axios.post(`${API_URL}/api/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        this.uploadedFile = response.data.file_name
        this.messages.push({
          type: 'system',
          content: `✅ 檔案上傳成功: ${response.data.file_name}`,
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
      } catch (error) {
        console.error('檔案上傳錯誤:', error)
        this.messages.push({
          type: 'system',
          content: '❌ 檔案上傳失敗',
          timestamp: new Date().toLocaleTimeString('zh-TW')
        })
      } finally {
        this.isLoading = false
        this.scrollToBottom()
      }
    },
    goToHealthCheck() {
      window.open('/status', '_blank')
    },
    getEmotionEmoji(emotion) {
      const emojis = {
        joy: '😊',
        sadness: '😢',
        anger: '😠',
        fear: '😰',
        love: '💛',
        tired: '😴',
        confused: '🤔',
        grateful: '🙏',
        neutral: '😐'
      }
      return emojis[emotion] || '😊'
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleString('zh-TW')
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const area = this.$refs.messagesArea
        if (area) {
          area.scrollTop = area.scrollHeight
        }
      })
    }
  }
}
</script>

<style scoped>
.chat-interface {
  display: grid;
  grid-template-columns: 1fr 350px;
  gap: 20px;
  height: 70vh;
}

.chat-container {
  display: flex;
  flex-direction: column;
  background: #f8f9fa;
  border-radius: 15px;
  overflow: hidden;
}

.messages-area {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.message {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  animation: slideIn 0.3s ease;
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

.message.assistant {
  align-self: flex-start;
}

.message.system {
  align-self: center;
}

.message-content {
  padding: 12px 16px;
  border-radius: 18px;
  position: relative;
}

.message.user .message-content {
  background: #667eea;
  color: white;
}

.message.assistant .message-content {
  background: #e9ecef;
  color: #333;
}

.message.system .message-content {
  background: #fff3cd;
  color: #856404;
}

.emotion-tag {
  display: inline-block;
  margin-top: 5px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  font-size: 0.85em;
}

.timestamp {
  font-size: 0.75em;
  color: #6c757d;
  margin-top: 4px;
  align-self: flex-end;
}

.loading {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.input-area {
  display: flex;
  gap: 10px;
  padding: 15px;
  background: white;
  border-top: 1px solid #dee2e6;
}

.input-area input {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid #e9ecef;
  border-radius: 25px;
  font-size: 1em;
  outline: none;
  transition: border-color 0.3s;
}

.input-area input:focus {
  border-color: #667eea;
}

.input-area button {
  padding: 12px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  font-size: 1em;
  transition: background 0.3s;
}

.input-area button:hover:not(:disabled) {
  background: #5568d3;
}

.input-area button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-upload-area {
  padding: 10px 15px;
  background: white;
  border-top: 1px solid #dee2e6;
  display: flex;
  gap: 10px;
  align-items: center;
}

.file-upload-area button {
  padding: 8px 16px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 15px;
  cursor: pointer;
  font-size: 0.9em;
}

.file-upload-area button:hover:not(:disabled) {
  background: #5a6268;
}

.file-upload-area button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-name {
  font-size: 0.9em;
  color: #495057;
}

.sidebar {
  background: #f8f9fa;
  border-radius: 15px;
  padding: 20px;
  overflow-y: auto;
}

.sidebar h3 {
  color: #495057;
  margin-bottom: 15px;
  font-size: 1.1em;
}

.memories-list {
  margin-bottom: 30px;
}

.memory-item {
  background: white;
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 10px;
  font-size: 0.9em;
}

.memory-item p {
  margin: 5px 0;
}

.memory-item small {
  color: #6c757d;
  font-size: 0.8em;
}

.emotion-chart {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.emotion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9em;
}

.intensity-bar {
  flex: 1;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.intensity-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s ease;
}
</style>
```
