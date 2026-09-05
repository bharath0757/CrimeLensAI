import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
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
