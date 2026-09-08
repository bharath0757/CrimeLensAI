import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { validateVercelApiOrigin } from "./config/api-origin.ts";

// https://vite.dev/config/
export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const rawApiOrigin = (process.env.VITE_API_BASE_URL || env.VITE_API_BASE_URL || "").trim();
  const isObsoleteOrigin = rawApiOrigin.includes("crimelensai-backend.onrender.com");
  const targetApiOrigin = (!rawApiOrigin || isObsoleteOrigin)
    ? "https://crimelensai-lmsi.onrender.com"
    : rawApiOrigin;

  if (command === "build" && (process.env.VERCEL ?? env.VERCEL) === "1") {
    validateVercelApiOrigin(targetApiOrigin);
  }
  const proxyTarget = env.API_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    define: command === "build" ? {
      "import.meta.env.VITE_API_BASE_URL": JSON.stringify(targetApiOrigin),
    } : undefined,
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      host: true, // Bind to 0.0.0.0 for Docker
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
