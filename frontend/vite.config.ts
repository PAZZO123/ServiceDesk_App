import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Default: the backend you run with uvicorn on 8001. Override with
// API_TARGET=http://127.0.0.1:8011 to point the dev server elsewhere.
const API_TARGET = process.env.API_TARGET ?? "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // REST, SSE and the WebSocket all live under /api.
      "/api": { target: API_TARGET, changeOrigin: true, ws: true },
      // The readiness probe sits outside /api (see app/main.py).
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
});
