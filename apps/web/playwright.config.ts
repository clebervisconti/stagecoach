import { defineConfig, devices } from "@playwright/test";

const port = 3100;
const baseURL = `http://localhost:${port}`;
const authSecret = process.env.AUTH_SECRET || "ci-build-placeholder-not-a-runtime-secret";

process.env.AUTH_URL = baseURL;
process.env.NEXTAUTH_URL = baseURL;

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
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium",
      dependencies: ["setup"],
      testIgnore: /auth\.setup\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth/member.json",
        launchOptions: { args: ["--disable-lcd-text"] },
      },
    },
  ],
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
      AUTH_URL: baseURL,
      NEXTAUTH_URL: baseURL,
      PRIVATE_BETA_MODE: "",
      PRIVATE_BETA_EMAIL: "",
      INTERNAL_API_URL: "http://127.0.0.1:9",
      OTEL_ENABLED: "false",
    },
  },
});
