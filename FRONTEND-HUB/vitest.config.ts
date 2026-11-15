import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // Keep jsdom/Radix tests stable alongside the Windows preview and compiler.
    maxWorkers: 2,
    testTimeout: 15_000,
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
