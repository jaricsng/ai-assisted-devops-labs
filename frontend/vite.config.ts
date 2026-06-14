import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    coverage: {
      provider: "v8",
      thresholds: { lines: 70, functions: 70, branches: 70, statements: 70 },
      exclude: ["src/test/**", "src/main.tsx", "src/api/types.ts"],
    },
  },
});
