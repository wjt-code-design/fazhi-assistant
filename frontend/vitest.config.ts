import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// 纯函数单测（执行书 T0.3）：node 环境即可，不需要 jsdom。
// resolve.alias 对齐 tsconfig paths（"@/*" → "./*"）。
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      // 只统计被测的三个纯模块，其余文件（含未测的组件/页面）不计入分母
      include: ["lib/annotate.ts", "lib/scope.ts", "lib/sse.ts"],
      reporter: ["text", "json-summary"],
      all: false,
    },
  },
});
