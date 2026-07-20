import { createApp } from 'vue';
import App from './App.vue';
import router from './router'; // <-- 加進行

// 前端未捕捉錯誤（不輸出敏感內容）
window.addEventListener('error', (event) => {
  console.error('[app-error]', event?.message || 'unknown');
});
window.addEventListener('unhandledrejection', (event) => {
  const reason = event?.reason;
  const msg = reason?.message || String(reason || 'unhandledrejection');
  console.error('[app-unhandled]', msg.slice(0, 200));
});

const app = createApp(App);
app.config.errorHandler = (err, _instance, info) => {
  console.error('[vue-error]', info, err?.message || err);
};
app.use(router);
app.mount('#app');
