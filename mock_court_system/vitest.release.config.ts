import { fileURLToPath } from "node:url"

import { defineConfig } from "vitest/config"

export default defineConfig({
  resolve: {
    alias: {
      // node_modules/next is a stripped install without `next/server`;
      // alias the minimal stub so BFF helpers remain unit-testable.
      "next/server": fileURLToPath(new URL("./tests/stubs/next-server.ts", import.meta.url)),
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["**/*.test.ts", "**/*.test.tsx"],
    exclude: [
      "components/hearing-3d/**",
      "e2e/**",
      "node_modules/**",
      ".next/**",
    ],
  },
})
