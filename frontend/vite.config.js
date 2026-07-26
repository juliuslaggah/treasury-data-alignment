import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss()],

  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },

  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },

  build: {
    target: "es2022",
    sourcemap: false,
  },
});

