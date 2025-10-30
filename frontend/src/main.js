import { createApp } from 'vue';
import App from './App.vue';
import router from './router'; // <-- 加進行
const app = createApp(App);
app.use(router);
app.mount('#app');
