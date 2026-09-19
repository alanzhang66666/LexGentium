import { defineConfig } from "@playwright/test"

const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT || 3000)
const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 8017)

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  // Managed backend lifecycle: spawn FastAPI with an isolated runtime data
  // root and deterministic mock LLM provider; killed and cleaned on teardown.
  globalSetup: "./e2e/harness/global-setup.ts",
  globalTeardown: "./e2e/harness/global-teardown.ts",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
  },
  // Managed frontend: Playwright starts and stops it inside the same command.
  webServer: {
    command: `npm run dev -- -p ${FRONTEND_PORT}`,
    url: `http://127.0.0.1:${FRONTEND_PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      BACKEND_URL: `http://127.0.0.1:${BACKEND_PORT}`,
      API_TOKEN: "e2e-token",
      PORT: String(FRONTEND_PORT),
    },
  },
  projects: [
    {
      name: "journey",
      testDir: "./e2e/journey",
      use: { browserName: "chromium" },
    },
    {
      name: "legacy-redirect",
      testDir: "./e2e",
      testMatch: "legacy-court3d-redirect.spec.ts",
      use: { browserName: "chromium" },
    },
    {
      name: "performance",
      testDir: "./e2e/perf",
      // Cold-navigation sampling must be serial: parallel workers would
      // contend on the network profile and skew durations.
      fullyParallel: false,
      workers: 1,
      use: { browserName: "chromium" },
    },
  ],
})
