<template>
  <div v-if="visible" class="history-overlay" @click.self="$emit('close')">
    <div class="history-panel">
      <header class="history-header">
        <div>
          <h2>📚 對話歷史</h2>
          <p class="sub">搜尋、總結、刪除與載入過去的對話</p>
        </div>
        <button type="button" class="close-btn" @click="$emit('close')">✕</button>
      </header>

      <div class="toolbar">
        <input
          v-model.trim="searchQuery"
          class="search-input"
          type="search"
          placeholder="搜尋歷史訊息關鍵字…"
          @keyup.enter="runSearch"
        />
        <button type="button" class="btn primary" :disabled="loading" @click="runSearch">
          搜尋
        </button>
        <button type="button" class="btn" :disabled="loading" @click="loadList">
          重新整理
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="info" class="info">{{ info }}</p>

      <div class="body">
        <!-- 左側列表 -->
        <aside class="list-pane">
          <div v-if="loading && !conversations.length" class="empty">載入中…</div>
          <div v-else-if="!displayList.length" class="empty">尚無對話紀錄</div>
          <button
            v-for="c in displayList"
            :key="c.conversation_id"
            type="button"
            class="conv-item"
            :class="{ active: selectedId === c.conversation_id }"
            @click="selectConversation(c.conversation_id)"
          >
            <div class="conv-title">{{ c.title || shortId(c.conversation_id) }}</div>
            <div class="conv-preview">{{ c.preview || c.snippet || '—' }}</div>
            <div class="conv-meta">
              <span>{{ c.message_count != null ? c.message_count + ' 則' : '' }}</span>
              <span>{{ formatTime(c.last_at || c.created_at) }}</span>
            </div>
          </button>
        </aside>

        <!-- 右側詳情 -->
        <section class="detail-pane">
          <div v-if="!selectedId" class="empty">選擇左側對話以查看內容</div>
          <template v-else>
            <div class="detail-actions">
              <button
                type="button"
                class="btn primary"
                :disabled="busy"
                @click="loadIntoChat"
              >
                載入到聊天
              </button>
              <button type="button" class="btn" :disabled="busy" @click="summarize">
                {{ summarizing ? '總結中…' : 'AI 總結' }}
              </button>
              <button type="button" class="btn danger" :disabled="busy" @click="remove">
                刪除對話
              </button>
            </div>

            <div v-if="summaryText" class="summary-box">
              <h3>✨ AI 總結</h3>
              <pre>{{ summaryText }}</pre>
            </div>

            <div class="messages" ref="msgBox">
              <div v-if="detailLoading" class="empty">載入訊息中…</div>
              <div
                v-for="(m, i) in detailMessages"
                :key="i"
                :class="['msg', m.type]"
              >
                <div class="msg-role">{{ m.type === 'user' ? '你' : '小宸光' }}</div>
                <div class="msg-body">{{ m.content }}</div>
                <div class="msg-time">{{ m.timestamp }}</div>
              </div>
            </div>
          </template>
        </section>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { API_BASE, getAuthHeaders } from '../config.js'
import { getUserAuthHeaders } from '../lib/auth.js'

export default {
  name: 'HistoryPanel',
  props: {
    visible: { type: Boolean, default: false },
    userId: { type: String, required: true },
    apiBase: { type: String, default: '' },
  },
  emits: ['close', 'load-conversation'],
  data() {
    return {
      conversations: [],
      searchHits: [],
      searchMode: false,
      searchQuery: '',
      selectedId: null,
      detailMessages: [],
      summaryText: '',
      loading: false,
      detailLoading: false,
      summarizing: false,
      busy: false,
      error: '',
      info: '',
    }
  },
  computed: {
    base() {
      return (this.apiBase || API_BASE || '').replace(/\/$/, '')
    },
    displayList() {
      if (this.searchMode && this.searchHits.length) {
        // 依 conversation 去重，保留最新 hit 當 preview
        const map = new Map()
        for (const h of this.searchHits) {
          const id = h.conversation_id
          if (!map.has(id)) {
            map.set(id, {
              conversation_id: id,
              title: (h.user_message || h.snippet || id).slice(0, 28),
              preview: h.snippet || h.user_message || h.assistant_message,
              last_at: h.created_at,
              message_count: null,
            })
          }
        }
        return Array.from(map.values())
      }
      return this.conversations
    },
  },
  watch: {
    visible(v) {
      if (v) {
        this.error = ''
        this.info = ''
        this.loadList()
      }
    },
  },
  methods: {
    shortId(id) {
      if (!id) return ''
      return id.length > 18 ? id.slice(0, 16) + '…' : id
    },
    formatTime(ts) {
      if (!ts) return ''
      return String(ts).replace('T', ' ').slice(0, 16)
    },
    async headers() {
      try {
        return await getUserAuthHeaders()
      } catch {
        return getAuthHeaders()
      }
    },
    async loadList() {
      this.loading = true
      this.error = ''
      this.searchMode = false
      this.searchHits = []
      try {
        const headers = await this.headers()
        const { data } = await axios.get(
          `${this.base}/api/history/conversations`,
          {
            params: { user_id: this.userId, limit: 50 },
            headers,
          }
        )
        this.conversations = data.conversations || []
        this.info = `共 ${data.total ?? this.conversations.length} 段對話`
      } catch (e) {
        this.error =
          e.response?.data?.detail || e.message || '載入對話列表失敗'
      } finally {
        this.loading = false
      }
    },
    async runSearch() {
      if (!this.searchQuery) {
        this.searchMode = false
        return this.loadList()
      }
      this.loading = true
      this.error = ''
      try {
        const headers = await this.headers()
        const { data } = await axios.get(`${this.base}/api/history/search`, {
          params: { user_id: this.userId, q: this.searchQuery, limit: 40 },
          headers,
        })
        this.searchHits = data.hits || []
        this.searchMode = true
        this.info = `找到 ${data.total_hits || 0} 筆相符訊息`
        if (!this.searchHits.length) {
          this.info = '沒有符合的結果'
        }
      } catch (e) {
        this.error = e.response?.data?.detail || e.message || '搜尋失敗'
      } finally {
        this.loading = false
      }
    },
    async selectConversation(id) {
      this.selectedId = id
      this.summaryText = ''
      this.detailLoading = true
      this.error = ''
      try {
        const headers = await this.headers()
        const { data } = await axios.get(
          `${this.base}/api/history/conversations/${encodeURIComponent(id)}`,
          {
            params: { user_id: this.userId, limit: 120 },
            headers,
          }
        )
        this.detailMessages = data.messages || []
      } catch (e) {
        this.error = e.response?.data?.detail || e.message || '載入對話失敗'
        this.detailMessages = []
      } finally {
        this.detailLoading = false
      }
    },
    loadIntoChat() {
      if (!this.selectedId) return
      this.$emit('load-conversation', {
        conversationId: this.selectedId,
        messages: this.detailMessages,
      })
      this.$emit('close')
    },
    async summarize() {
      if (!this.selectedId) return
      this.summarizing = true
      this.busy = true
      this.error = ''
      try {
        const headers = await this.headers()
        const { data } = await axios.post(
          `${this.base}/api/history/summarize`,
          {
            conversation_id: this.selectedId,
            user_id: this.userId,
            max_messages: 40,
          },
          { headers }
        )
        this.summaryText = data.summary || '（無摘要）'
        this.info = '總結完成'
      } catch (e) {
        this.error =
          e.response?.data?.detail || e.message || 'AI 總結失敗'
      } finally {
        this.summarizing = false
        this.busy = false
      }
    },
    async remove() {
      if (!this.selectedId) return
      if (
        !confirm(
          '確定要永久刪除這段對話嗎？此操作無法復原。'
        )
      ) {
        return
      }
      this.busy = true
      this.error = ''
      try {
        const headers = await this.headers()
        await axios.delete(
          `${this.base}/api/history/conversations/${encodeURIComponent(this.selectedId)}`,
          {
            params: { user_id: this.userId },
            headers,
          }
        )
        const deletedId = this.selectedId
        this.info = '已刪除對話'
        this.selectedId = null
        this.detailMessages = []
        this.summaryText = ''
        await this.loadList()
        this.$emit('conversation-deleted', deletedId)
      } catch (e) {
        this.error = e.response?.data?.detail || e.message || '刪除失敗'
      } finally {
        this.busy = false
      }
    },
  },
}
</script>

<style scoped>
.history-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(4px);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.history-panel {
  width: min(1100px, 100%);
  height: min(85vh, 800px);
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.1rem 1.25rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.history-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.sub {
  margin: 0.25rem 0 0;
  opacity: 0.9;
  font-size: 0.85rem;
}

.close-btn {
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 1rem;
}

.toolbar {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e5e7eb;
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 180px;
  padding: 0.55rem 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  font-size: 0.95rem;
}

.btn {
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 10px;
  padding: 0.5rem 0.85rem;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
}

.btn.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
}

.btn.danger {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fecaca;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.error {
  margin: 0.5rem 1rem 0;
  color: #b91c1c;
  background: #fef2f2;
  border-radius: 8px;
  padding: 0.45rem 0.7rem;
  font-size: 0.85rem;
}

.info {
  margin: 0.5rem 1rem 0;
  color: #065f46;
  font-size: 0.85rem;
}

.body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.list-pane {
  width: 34%;
  min-width: 220px;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
  background: #fafafa;
}

.conv-item {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  border-bottom: 1px solid #eee;
  background: transparent;
  padding: 0.75rem 0.9rem;
  cursor: pointer;
}

.conv-item:hover,
.conv-item.active {
  background: #eef2ff;
}

.conv-title {
  font-weight: 700;
  color: #1f2937;
  font-size: 0.92rem;
  margin-bottom: 0.2rem;
}

.conv-preview {
  font-size: 0.8rem;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  margin-top: 0.3rem;
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  color: #9ca3af;
}

.detail-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  padding: 0.65rem 0.9rem;
  border-bottom: 1px solid #e5e7eb;
}

.summary-box {
  margin: 0.65rem 0.9rem 0;
  padding: 0.75rem;
  background: #f5f3ff;
  border: 1px solid #ddd6fe;
  border-radius: 12px;
  max-height: 28%;
  overflow-y: auto;
}

.summary-box h3 {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
  color: #5b21b6;
}

.summary-box pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 0.88rem;
  color: #374151;
  line-height: 1.5;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.msg {
  max-width: 90%;
  padding: 0.65rem 0.85rem;
  border-radius: 14px;
  font-size: 0.9rem;
}

.msg.user {
  align-self: flex-end;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.msg.assistant {
  align-self: flex-start;
  background: #f3f4f6;
  color: #1f2937;
}

.msg-role {
  font-size: 0.72rem;
  opacity: 0.8;
  margin-bottom: 0.2rem;
  font-weight: 700;
}

.msg-body {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.45;
}

.msg-time {
  margin-top: 0.25rem;
  font-size: 0.7rem;
  opacity: 0.7;
}

.empty {
  padding: 2rem 1rem;
  text-align: center;
  color: #9ca3af;
  font-size: 0.9rem;
}

@media (max-width: 720px) {
  .body {
    flex-direction: column;
  }
  .list-pane {
    width: 100%;
    max-height: 35%;
  }
}
</style>
