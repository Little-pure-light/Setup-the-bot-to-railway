import { createRouter, createWebHistory } from 'vue-router';
import ChatInterface from '../components/ChatInterface.vue';
import StatusPage from '../components/StatusPage.vue';

const routes = [
  { path: '/', component: ChatInterface },
  { path: '/status', component: StatusPage },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
