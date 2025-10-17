<template>
  <div id="app">
    <div class="header">
      <img alt="logo" src="./assets/logo.png" class="logo" />
      <div class="title">小宸光・AI靈魂對話</div>
    </div>

    <router-view />

    <div class="footer">
      <button @click="goToHealthCheck">健康狀態檢查</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'App',
  methods: {
    goToHealthCheck() {
      window.open('/status', '_blank');
    },
  },
};
</script>

<style>
#app {
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 0;
}

.header {
  background-color: #35495e;
  padding: 1em;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo {
  height: 40px;
  margin-right: 1em;
}

.title {
  font-size: 1.5em;
  font-weight: bold;
}

.footer {
  position: fixed;
  bottom: 0;
  width: 100%;
  background: #ecf0f1;
  padding: 0.5em;
  text-align: center;
}

.footer button {
  padding: 0.5em 1em;
  font-size: 1em;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.footer button:hover {
  background-color: #38a173;
}
</style>
