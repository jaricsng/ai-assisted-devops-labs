import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    exclude: ["node_modules", "e2e/**"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
      thresholds: { lines: 70, functions: 70, branches: 70, statements: 70 },
      exclude: [
        "src/test/**",
        "src/main.tsx",
        "src/api/types.ts",
        "e2e/**",
        "**/*.config.ts",
      ],
    },
  },
});
