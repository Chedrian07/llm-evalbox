import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.EVALBOX_E2E_PORT ?? 8765);
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./flows",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Boot the FastAPI server in front of the (already-built) SPA bundle.
    // Skipped in CI when EVALBOX_E2E_NO_SERVER=1 (pre-started elsewhere).
    command: process.env.EVALBOX_E2E_NO_SERVER
      ? "echo 'EVALBOX_E2E_NO_SERVER=1, expecting external server'"
      : `python -m llm_evalbox web --host 127.0.0.1 --port ${PORT} --no-open`,
    url: `${BASE_URL}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
