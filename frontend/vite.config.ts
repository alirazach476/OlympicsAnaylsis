/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: { output: { manualChunks: {
      react: ["react", "react-dom", "react-router-dom"], charts: ["recharts"], motion: ["framer-motion"], tanstack: ["@tanstack/react-table", "@tanstack/react-virtual", "@tanstack/react-query"],
    } } },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], testTimeout: 30000, css: false },
});
