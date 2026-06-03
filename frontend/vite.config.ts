import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      workbox: {
        // Don't let the SW's SPA navigation fallback swallow real server
        // navigations (OAuth redirects to /api/..., the health probe). Without
        // this, clicking "Connect with Google" is served index.html instead of
        // hitting the 307 to Google, bouncing you back into the app root.
        navigateFallbackDenylist: [/^\/api\//, /^\/health$/, /^\/docs$/],
      },
      manifest: {
        name: "Training App",
        short_name: "Training",
        description: "Personal training, nutrition and health hub",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/",
      },
    }),
  ],
  server: {
    // Dev proxy so the SPA can call the API on :8000 without CORS fuss.
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
