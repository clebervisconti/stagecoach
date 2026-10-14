import { defineConfig, devices } from "@playwright/test";

const port = 3100;
const baseURL = `http://localhost:${port}`;
const authSecret = process.env.AUTH_SECRET || "ci-build-placeholder-not-a-runtime-secret";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: process.env.CI
      ? `npx next start -H localhost -p ${port}`
      : `npx next dev -H localhost -p ${port}`,
    url: `${baseURL}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      AUTH_SECRET: authSecret,
      PRIVATE_BETA_MODE: "true",
      PRIVATE_BETA_EMAIL: "ci@example.invalid",
      INTERNAL_API_URL: "http://127.0.0.1:9",
      OTEL_ENABLED: "false",
    },
  },
});
