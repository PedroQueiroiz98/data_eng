/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const backendOrigin = process.env.VITE_BACKEND_ORIGIN ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: backendOrigin, changeOrigin: true },
      "/ready": { target: backendOrigin, changeOrigin: true },
      "/health": { target: backendOrigin, changeOrigin: true },
      "/ws": { target: backendOrigin, changeOrigin: true, ws: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // `monaco-editor` real é ESM pesado e não resolve no jsdom — stub nos testes.
    alias: { "monaco-editor": path.resolve(__dirname, "src/test/monacoMock.ts") },
  },
});
