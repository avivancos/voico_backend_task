/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/components/ui/**", // vendored shadcn primitives
        "src/main.tsx",
        "src/App.tsx", // trivial composition root
        "src/test/**",
        "src/test-utils.tsx",
        "**/*.d.ts",
        "**/__tests__/**",
      ],
      thresholds: { lines: 90, functions: 85, branches: 85, statements: 90 },
    },
  },
});
