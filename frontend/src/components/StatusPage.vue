<template>
  <div class="status-page">
    <h1 class="title">訊息服務健康狀態檢查結果</h1>
    <ul v-if="status">
      <li>
        <strong>Backend:</strong>
        <span :class="{ healthy: status.backend, unhealthy: !status.backend }">
          {{ status.backend ? '正常' : '當機不可用' }}
        </span>
      </li>
      <li>
        <strong>Database:</strong>
        <span :class="{ healthy: status.database, unhealthy: !status.database }">
          {{ status.database ? '正常' : '當機不可用' }}
        </span>
      </li>
      <li>
        <strong>OpenAI API:</strong>
        <span :class="{ healthy: status.openai, unhealthy: !status.openai }">
          {{ status.openai ? '正常' : '當機不可用' }}
        </span>
      </li>
    </ul>
    <div v-else>
      <p>正在取得服務狀態資訊...</p>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      status: null
    }
  },
  mounted() {
    fetch('/status')
      .then(res => res.json())
      .then(data => {
        this.status = data
      })
      .catch(error => {
        console.error('操作失敗:', error)
        this.status = {
          backend: false,
          database: false,
          openai: false
        }
      })
  }
}
</script>

<style scoped>
.status-page {
  max-width: 600px;
  margin: 0 auto;
  padding: 2rem;
  font-family: Arial, sans-serif;
  background: #f9f9f9;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
.title {
  font-size: 1.8rem;
  margin-bottom: 1.5rem;
  color: #333;
  text-align: center;
}
ul {
  list-style: none;
  padding: 0;
}
li {
  margin-bottom: 1rem;
  font-size: 1.2rem;
}
.healthy {
  color: green;
  font-weight: bold;
}
.unhealthy {
  color: red;
  font-weight: bold;
}
</style>
