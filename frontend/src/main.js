import { createApp } from 'vue';
import App from './App.vue';
import router from './router'; // <-- 加進行
import { logClientError } from './lib/errorSanitize.js';

// 前端未捕捉錯誤：僅輸出脫敏摘要，不直接 dump event.message / reason.message
window.addEventListener('error', (event) => {
  logClientError('[app-error]', event?.error || { name: 'Error', message: 'window.error' }, {
    info: event?.filename ? String(event.filename).split('/').pop() : 'window',
  });
});
window.addEventListener('unhandledrejection', (event) => {
  logClientError('[app-unhandled]', event?.reason || { name: 'UnhandledRejection' }, {
    info: 'promise',
  });
});

const app = createApp(App);
app.config.errorHandler = (err, _instance, info) => {
  logClientError('[vue-error]', err, { info: info || 'vue' });
};
app.use(router);
app.mount('#app');
