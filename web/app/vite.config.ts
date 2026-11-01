import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// The API is the same origin by default (the home computer serves both); `npm run dev` proxies /api.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Chess Coach", short_name: "Coach", start_url: ".", display: "standalone",
        background_color: "#eef2f4", theme_color: "#1f5fbf",
        icons: [{ src: "icon-192.png", sizes: "192x192", type: "image/png" }, { src: "icon-512.png", sizes: "512x512", type: "image/png" }],
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [{ urlPattern: ({ url }) => url.pathname.startsWith("/api/") && !url.pathname.endsWith("/login"),
          handler: "NetworkFirst", method: "GET", options: { cacheName: "api", networkTimeoutSeconds: 6 } }],
      },
    }),
  ],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
