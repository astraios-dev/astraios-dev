import { defineConfig } from "vite";

export default defineConfig({
  root: "app",
  publicDir: "../public",
  build: {
    outDir: "../site",
    emptyOutDir: true,
    assetsDir: "assets",
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  appType: "spa",
});
