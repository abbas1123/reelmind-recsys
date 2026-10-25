import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Vite's default "localhost" binds only ::1 on Windows, so the documented http://127.0.0.1:5173 was refused.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: API, changeOrigin: true } },
  },
  build: { chunkSizeWarningLimit: 800 }, // HeroUI + React Aria main chunk; dashboard is split out
  preview: {
    port: 4173,
    proxy: { "/api": { target: API, changeOrigin: true } },
  },
});
