import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      // /media 由 FastAPI StaticFiles 提供（见 backend/app/main.py），无需依赖本机 80 端口 nginx
      "/media": "http://localhost:8000",
    },
  },
});
