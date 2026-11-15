import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import { fileURLToPath, URL } from "node:url";

// Desktop-only static SPA. The original Lovable/SSR configuration stays separate.
export default defineConfig({
  plugins: [tanstackRouter({ target: "react", autoCodeSplitting: false }), react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
    proxy:
      process.env.NOVELIS_PREVIEW_ROLE === "finance"
        ? {
            "/api": { target: "http://127.0.0.1:18037", changeOrigin: true },
          }
        : undefined,
  },
  build: { outDir: "dist-desktop", emptyOutDir: true, target: "es2022" },
});
