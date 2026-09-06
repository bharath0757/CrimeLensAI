import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { validateVercelApiOrigin } from "./config/api-origin.ts";

// https://vite.dev/config/
export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), "");
  if (command === "build" && (process.env.VERCEL ?? env.VERCEL) === "1") {
    validateVercelApiOrigin(process.env.VITE_API_BASE_URL ?? env.VITE_API_BASE_URL);
  }
  const proxyTarget = env.API_PROXY_TARGET;
  return {
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true, // Bind to 0.0.0.0 for Docker
    proxy: proxyTarget ? {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    } : undefined,
  },
  };
});
