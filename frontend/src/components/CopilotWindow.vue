<template>
  <div class="copilot-window" v-if="isVisible">
    <div class="copilot-overlay" @click="closeWindow"></div>
    <div class="copilot-container">
      <!-- Header -->
      <div class="copilot-header">
        <div class="header-title">
          <span class="icon">🤖</span>
          <h2>Ask Copilot</h2>
        </div>
        <button class="close-btn" @click="closeWindow">✕</button>
      </div>

      <!-- Content -->
      <div class="copilot-body">
        <!-- Input Section -->
        <div class="input-section">
          <textarea
            v-model="userPrompt"
            placeholder="詢問 Copilot 任何程式相關問題..."
            rows="4"
            @keydown.ctrl.enter="askCopilot"
          ></textarea>
          
          <div class="input-meta">
            <input
              v-model="fileName"
              type="text"
              placeholder="檔案名稱（選填）"
              class="file-input"
            />
            <button
              @click="askCopilot"
              :disabled="isProcessing || !userPrompt.trim()"
              class="ask-btn"
            >
              {{ isProcessing ? '處理中...' : '發送' }}
            </button>
          </div>
        </div>

        <!-- Status Display -->
        <div v-if="sessionId" class="status-section">
          <div class="status-badge" :class="statusClass">
            {{ statusText }}
          </div>
          <div class="session-info">Session: {{ sessionId }}</div>
        </div>

        <!-- Memory Summary -->
        <div v-if="memorySummary" class="section memory-section">
          <h3>🧠 記憶摘要</h3>
          <div class="memory-content">
            <div class="memory-item">
              <span class="label">最近記憶:</span>
              <span class="value">{{ memorySummary.recent_count }} 筆</span>
            </div>
            <div class="memory-item">
              <span class="label">人格特質:</span>
              <span class="value">{{ memorySummary.personality }}</span>
            </div>
            <div class="memory-item">
              <span class="label">記憶 ID:</span>
              <span class="value">{{ memorySummary.memory_id }}</span>
            </div>
          </div>
        </div>

        <!-- Copilot Reply -->
        <div v-if="copilotReply" class="section reply-section">
          <h3>💬 Copilot 回覆</h3>
          <div class="reply-content">
            {{ copilotReply }}
          </div>
        </div>

        <!-- Reflection -->
        <div v-if="reflection" class="section reflection-section">
          <h3>💭 反思摘要</h3>
          <div class="reflection-content">
            <p>{{ reflection.content }}</p>
            <div class="reflection-meta">
              <span class="confidence">信心度: {{ (reflection.confidence * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>

        <!-- Error Display -->
        <div v-if="errorMessage" class="error-section">
          ❌ {{ errorMessage }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { COPILOT_API_BASE } from '../config.js'

export default {
  name: 'CopilotWindow',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    conversationId: {
      type: String,
      required: true
    },
    userId: {
      type: String,
      default: 'default_user'
    }
  },
  data() {
    return {
      userPrompt: '',
      fileName: '',
      isProcessing: false,
      sessionId: '',
      status: '',
      copilotReply: '',
      memorySummary: null,
      reflection: null,
      errorMessage: ''
    }
  },
  computed: {
    isVisible() {
      return this.visible
    },
    statusClass() {
      return {
        'processing': this.status === 'processing',
        'completed': this.status === 'completed',
        'failed': this.status === 'failed'
      }
    },
    statusText() {
      const statusMap = {
        'processing': '⏳ 處理中...',
        'completed': '✅ 完成',
        'failed': '❌ 失敗'
      }
      return statusMap[this.status] || '待處理'
    }
  },
  methods: {
    closeWindow() {
      this.$emit('close')
      this.resetForm()
    },
    
    resetForm() {
      this.userPrompt = ''
      this.fileName = ''
      this.sessionId = ''
      this.status = ''
      this.copilotReply = ''
      this.memorySummary = null
      this.reflection = null
      this.errorMessage = ''
    },
    
    async askCopilot() {
      if (!this.userPrompt.trim()) return
      
      this.isProcessing = true
      this.status = 'processing'
      this.errorMessage = ''
      
      try {
        const COPILOT_API = `${COPILOT_API_BASE}/api/ask_copilot`
        
        const response = await axios.post(COPILOT_API, {
          prompt: this.userPrompt,
          conversation_id: this.conversationId,
          user_id: this.userId,
          file_name: this.fileName || null
        }, {
          timeout: 60000
        })
        
        if (response.status === 200) {
          const data = response.data
          
          this.sessionId = data.session_id
          this.status = data.status
          this.copilotReply = data.copilot_reply
          this.memorySummary = data.memory_summary
          this.reflection = data.reflection
          
          console.log('✅ Copilot 回覆成功:', data)
        }
        
      } catch (error) {
        console.error('❌ Copilot 請求失敗:', error)
        this.status = 'failed'
        this.errorMessage = error.response?.data?.detail || error.message || 'Copilot 請求失敗'
      } finally {
        this.isProcessing = false
      }
    }
  }
}
</script>

<style scoped>
.copilot-window {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  display: flex;
  justify-content: center;
  align-items: center;
}

.copilot-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(5px);
}

.copilot-container {
  position: relative;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  background: white;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.copilot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title .icon {
  font-size: 28px;
}

.header-title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  font-size: 24px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.1);
}

.copilot-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.input-section {
  margin-bottom: 20px;
}

.input-section textarea {
  width: 100%;
  padding: 12px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.2s;
}

.input-section textarea:focus {
  outline: none;
  border-color: #667eea;
}

.input-meta {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.file-input {
  flex: 1;
  padding: 10px 12px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
}

.file-input:focus {
  outline: none;
  border-color: #667eea;
}

.ask-btn {
  padding: 10px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.ask-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.ask-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.status-section {
  margin-bottom: 20px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
}

.status-badge.processing {
  background: #fff3cd;
  color: #856404;
}

.status-badge.completed {
  background: #d4edda;
  color: #155724;
}

.status-badge.failed {
  background: #f8d7da;
  color: #721c24;
}

.session-info {
  font-size: 12px;
  color: #666;
  font-family: monospace;
}

.section {
  margin-bottom: 20px;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.section h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #333;
}

.memory-section {
  background: #f0f7ff;
  border-color: #b3d9ff;
}

.memory-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memory-item {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.memory-item .label {
  color: #666;
  font-weight: 500;
}

.memory-item .value {
  color: #333;
  font-weight: 600;
}

.reply-section {
  background: #fff;
  border-color: #667eea;
}

.reply-content {
  color: #333;
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 14px;
}

.reflection-section {
  background: #f9f0ff;
  border-color: #d9b3ff;
}

.reflection-content p {
  margin: 0 0 8px 0;
  color: #333;
  line-height: 1.6;
  font-size: 14px;
}

.reflection-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.confidence {
  font-weight: 600;
}

.error-section {
  padding: 12px;
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 8px;
  color: #721c24;
  font-size: 14px;
}
</style>
