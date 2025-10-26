import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
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
