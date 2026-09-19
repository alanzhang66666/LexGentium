import { defineConfig } from "vitest/config"

export default defineConfig({
  test: {
    environment: "node",
    include: ["components/hearing-3d/**/*.test.ts", "lib/**/*.test.ts"],
  },
})
