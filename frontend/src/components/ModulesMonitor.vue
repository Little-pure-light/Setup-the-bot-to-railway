<template>
  <div class="modules-monitor">
    <div class="header">
      <h1>🧠 XiaoChenGuang AI - 模組監控儀表板</h1>
      <button @click="refreshStatus" class="refresh-btn" :disabled="loading">
        {{ loading ? '正在更新...' : '🔄 刷新' }}
      </button>
    </div>

    <!-- 系統總覽 -->
    <div v-if="systemInfo" class="system-info">
      <h2>📊 系統總覽</h2>
      <div class="info-grid">
        <div class="info-card">
          <span class="label">系統名稱</span>
          <span class="value">{{ systemInfo.name }}</span>
        </div>
        <div class="info-card">
          <span class="label">版本</span>
          <span class="value">{{ systemInfo.version }}</span>
        </div>
        <div class="info-card">
          <span class="label">階段</span>
          <span class="value">{{ systemInfo.phase }}</span>
        </div>
      </div>
    </div>

    <!-- 環境狀態 -->
    <div v-if="environment" class="environment-section">
      <h2>🔧 環境配置</h2>
      <div class="env-grid">
        <div v-for="(status, key) in environment" :key="key" class="env-item">
          <span class="env-key">{{ key }}</span>
          <span :class="['env-status', getStatusClass(status)]">{{ status }}</span>
        </div>
      </div>
    </div>

    <!-- 模組狀態 -->
    <div v-if="modules && modules.length > 0" class="modules-section">
      <h2>🎯 核心模組狀態</h2>
      <div class="modules-grid">
        <div v-for="module in modules" :key="module.name" 
             :class="['module-card', getModuleStatusClass(module)]">
          <div class="module-header">
            <h3>{{ getModuleIcon(module.name) }} {{ getModuleName(module.name) }}</h3>
            <span :class="['module-status-badge', module.enabled ? 'enabled' : 'disabled']">
              {{ module.enabled ? '✅ 啟用' : '❌ 停用' }}
            </span>
          </div>
          
          <div class="module-body">
            <div class="module-info">
              <div class="info-row">
                <span class="info-label">健康狀態:</span>
                <span :class="['info-value', module.status === 'healthy' ? 'healthy' : 'unhealthy']">
                  {{ module.status === 'healthy' ? '✅ 正常' : '⚠️ 異常' }}
                </span>
              </div>
              
              <!-- 記憶模組專屬資訊 -->
              <div v-if="module.name === 'memory' && module.stats" class="module-stats">
                <div class="stat-item">
                  <span class="stat-label">Redis 快取:</span>
                  <span class="stat-value">{{ module.stats.redis_count || 0 }} 筆</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Supabase 記錄:</span>
                  <span class="stat-value">{{ module.stats.supabase_count || 0 }} 筆</span>
                </div>
              </div>

              <!-- 反思模組專屬資訊 -->
              <div v-if="module.name === 'reflection' && module.total_reflections !== undefined" class="module-stats">
                <div class="stat-item">
                  <span class="stat-label">總反思次數:</span>
                  <span class="stat-value">{{ module.total_reflections }}</span>
                </div>
                <div v-if="module.avg_confidence" class="stat-item">
                  <span class="stat-label">平均置信度:</span>
                  <span class="stat-value">{{ (module.avg_confidence * 100).toFixed(1) }}%</span>
                </div>
              </div>

              <!-- 行為調節模組專屬資訊 -->
              <div v-if="module.name === 'behavior' && module.personality_vector" class="module-stats">
                <h4>人格向量:</h4>
                <div class="personality-bars">
                  <div v-for="(value, trait) in module.personality_vector" :key="trait" class="trait-bar">
                    <span class="trait-name">{{ getTraitName(trait) }}</span>
                    <div class="bar-container">
                      <div class="bar-fill" :style="{width: (value * 100) + '%'}"></div>
                    </div>
                    <span class="trait-value">{{ (value * 100).toFixed(0) }}%</span>
                  </div>
                </div>
                <div v-if="module.total_adjustments" class="stat-item">
                  <span class="stat-label">調整次數:</span>
                  <span class="stat-value">{{ module.total_adjustments }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 無模組數據 -->
    <div v-else-if="!loading" class="no-data">
      <p>⚠️ 無法獲取模組資訊，請確認後端服務正常運行</p>
    </div>

    <!-- 載入中 -->
    <div v-if="loading" class="loading">
      <p>🔄 正在載入系統狀態...</p>
    </div>

    <!-- 錯誤訊息 -->
    <div v-if="error" class="error-message">
      <p>❌ 錯誤: {{ error }}</p>
    </div>

    <!-- 最後更新時間 -->
    <div v-if="lastUpdate" class="last-update">
      最後更新: {{ lastUpdate }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'ModulesMonitor',
  data() {
    return {
      systemInfo: null,
      environment: null,
      modules: [],
      loading: true,
      error: null,
      lastUpdate: null,
      autoRefresh: null
    }
  },
  mounted() {
    this.fetchStatus()
    // 每30秒自動刷新
    this.autoRefresh = setInterval(() => {
      this.fetchStatus()
    }, 30000)
  },
  beforeUnmount() {
    if (this.autoRefresh) {
      clearInterval(this.autoRefresh)
    }
  },
  methods: {
    async fetchStatus() {
      this.loading = true
      this.error = null
      
      try {
        const response = await fetch('/api/health/detailed')
        const data = await response.json()
        
        if (data.system) {
          this.systemInfo = data.system
        }
        
        if (data.environment) {
          this.environment = data.environment
        }
        
        if (data.modules) {
          // 將模組物件轉為陣列
          this.modules = Object.keys(data.modules).map(key => ({
            name: key,
            ...data.modules[key]
          }))
        }
        
        this.lastUpdate = new Date().toLocaleString('zh-TW')
      } catch (err) {
        this.error = err.message || '無法連接到後端服務'
        console.error('獲取狀態失敗:', err)
      } finally {
        this.loading = false
      }
    },
    refreshStatus() {
      this.fetchStatus()
    },
    getStatusClass(status) {
      if (status === '✅') return 'status-ok'
      if (status.includes('⚠️')) return 'status-warning'
      return 'status-error'
    },
    getModuleStatusClass(module) {
      if (!module.enabled) return 'module-disabled'
      if (module.status === 'healthy') return 'module-healthy'
      return 'module-error'
    },
    getModuleIcon(name) {
      const icons = {
        memory: '💾',
        reflection: '🧠',
        behavior: '🎯',
        knowledge: '📚',
        knowledge_hub: '📚'
      }
      return icons[name] || '📦'
    },
    getModuleName(name) {
      const names = {
        memory: '記憶模組',
        reflection: '反思模組',
        behavior: '行為調節模組',
        knowledge: '知識中樞',
        knowledge_hub: '知識中樞'
      }
      return names[name] || name
    },
    getTraitName(trait) {
      const names = {
        empathy: '同理心',
        curiosity: '好奇心',
        humor: '幽默感',
        technical_depth: '技術深度',
        patience: '耐心',
        creativity: '創造力'
      }
      return names[trait] || trait
    }
  }
}
</script>

<style scoped>
.modules-monitor {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid #e0e0e0;
}

.header h1 {
  font-size: 1.8rem;
  color: #333;
  margin: 0;
}

.refresh-btn {
  padding: 0.6rem 1.2rem;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
  transition: background 0.3s;
}

.refresh-btn:hover:not(:disabled) {
  background: #45a049;
}

.refresh-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* 系統資訊 */
.system-info {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1.5rem;
  border-radius: 12px;
  margin-bottom: 2rem;
}

.system-info h2 {
  margin-top: 0;
  font-size: 1.3rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.info-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-card .label {
  font-size: 0.9rem;
  opacity: 0.9;
}

.info-card .value {
  font-size: 1.1rem;
  font-weight: bold;
}

/* 環境狀態 */
.environment-section {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 2rem;
}

.environment-section h2 {
  margin-top: 0;
  color: #333;
}

.env-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.env-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.8rem;
  background: #f5f5f5;
  border-radius: 6px;
}

.env-key {
  font-weight: 500;
  color: #555;
}

.env-status {
  font-weight: bold;
}

.status-ok {
  color: #4CAF50;
}

.status-warning {
  color: #ff9800;
}

.status-error {
  color: #f44336;
}

/* 模組區域 */
.modules-section h2 {
  color: #333;
  margin-bottom: 1.5rem;
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 1.5rem;
}

.module-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  overflow: hidden;
  transition: transform 0.3s, box-shadow 0.3s;
}

.module-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.module-healthy {
  border-left: 4px solid #4CAF50;
}

.module-disabled {
  border-left: 4px solid #999;
  opacity: 0.7;
}

.module-error {
  border-left: 4px solid #f44336;
}

.module-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

.module-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #333;
}

.module-status-badge {
  padding: 0.3rem 0.8rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: bold;
}

.module-status-badge.enabled {
  background: #e8f5e9;
  color: #2e7d32;
}

.module-status-badge.disabled {
  background: #f5f5f5;
  color: #757575;
}

.module-body {
  padding: 1.5rem;
}

.module-info {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-weight: 500;
  color: #666;
}

.info-value {
  font-weight: bold;
}

.info-value.healthy {
  color: #4CAF50;
}

.info-value.unhealthy {
  color: #f44336;
}

.module-stats {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e0e0e0;
}

.module-stats h4 {
  margin: 0 0 0.8rem 0;
  font-size: 0.9rem;
  color: #666;
  text-transform: uppercase;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
}

.stat-label {
  color: #666;
  font-size: 0.9rem;
}

.stat-value {
  font-weight: bold;
  color: #333;
}

/* 人格向量條 */
.personality-bars {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.trait-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.trait-name {
  min-width: 70px;
  font-size: 0.85rem;
  color: #666;
}

.bar-container {
  flex: 1;
  height: 20px;
  background: #e0e0e0;
  border-radius: 10px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #8BC34A);
  transition: width 0.5s ease;
}

.trait-value {
  min-width: 40px;
  text-align: right;
  font-size: 0.85rem;
  font-weight: bold;
  color: #333;
}

.loading, .no-data, .error-message {
  text-align: center;
  padding: 3rem;
  font-size: 1.1rem;
}

.error-message {
  color: #f44336;
  background: #ffebee;
  border-radius: 8px;
}

.last-update {
  text-align: center;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid #e0e0e0;
  color: #999;
  font-size: 0.9rem;
}
</style>
