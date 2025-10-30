import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
   // ✅ 添加這個
  define: {
    __API_URL__: JSON.stringify(process.env.VITE_API_URL || 'https://setup-the-bot-to-railway-production.up.railway.app')
  },
  envPrefix: 'VITE_',
  server: {
    host: "0.0.0.0", // 外網可訪問
    port: 5000, // 改用不衝突的端口
    strictPort: true,
    hmr: {
      clientPort: 443, // Replit thru HTTPS
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
    allowedHosts: true, // ❤️ 允許所有 host
  },
});
