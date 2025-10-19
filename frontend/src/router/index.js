import { createRouter, createWebHistory } from 'vue-router';
import ChatInterface from '../components/ChatInterface.vue';
import StatusPage from '../components/StatusPage.vue';
import ModulesMonitor from '../components/ModulesMonitor.vue';

const routes = [
  { path: '/', component: ChatInterface },
  { path: '/status', component: StatusPage },
  { path: '/monitor', component: ModulesMonitor },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
