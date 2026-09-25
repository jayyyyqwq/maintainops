import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to a deployed stack: VITE_API_PROXY=https://xxxx.cloudfront.net npm run dev
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: process.env.VITE_API_PROXY
      ? { "/api": { target: process.env.VITE_API_PROXY, changeOrigin: true } }
      : undefined,
  },
  build: { chunkSizeWarningLimit: 900 },
});
