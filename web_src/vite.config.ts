import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Backend default: 127.0.0.1:8765 (matches `evalbox web`).
const API_TARGET = process.env.EVALBOX_API_TARGET ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true, ws: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1000,
  },
});
