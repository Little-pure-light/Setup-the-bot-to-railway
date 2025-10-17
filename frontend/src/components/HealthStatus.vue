<template>
  <div class="health-status">
    <h2>健康狀態檢查</h2>
    <div v-if="status">
      <p><strong>API 狀態:</strong> {{ status.api_status }}</p>
      <p><strong>Supabase 連線:</strong> {{ status.supabase_connected }}</p>
      <p><strong>Memories Table:</strong> {{ status.memories_table }}</p>
      <p><strong>OpenAI Key:</strong> {{ status.openai_key }}</p>
    </div>
    <div v-else>
      <p>正在讀取健康狀態...</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'HealthStatus',
  data() {
    return {
      status: null
    }
  },
  mounted() {
    this.fetchHealthStatus()
  },
  methods: {
    async fetchHealthStatus() {
      try {
        const response = await fetch('/status')
        const data = await response.json()
        this.status = data
      } catch (error) {
        this.status = {
          api_status: 'Error',
          supabase_connected: 'Unknown',
          memories_table: 'Unknown',
          openai_key: 'Unknown'
        }
      }
    }
  }
}
</script>

<style scoped>
.health-status {
  padding: 20px;
  font-family: Arial, sans-serif;
  background: #f9f9f9;
  border-radius: 10px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}

.health-status h2 {
  margin-bottom: 10px;
}

.health-status p {
  margin: 6px 0;
}
</style>
