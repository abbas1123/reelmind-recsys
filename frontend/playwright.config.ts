import { defineConfig } from "@playwright/test";

// End-to-end tests drive the real app: FastAPI backend with the trained artifacts + Vite dev server.
// They use a separate SQLite file (data/e2e.db) so your own profiles stay untouched.
// Browser: the locally installed Microsoft Edge (no Playwright browser download needed).
// Set PW_CHANNEL=chrome to use Google Chrome, or PW_CHANNEL=chromium after `npx playwright install chromium`.
const channel = process.env.PW_CHANNEL ?? "msedge";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    channel: channel === "chromium" ? undefined : channel,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    colorScheme: "dark",
  },
  webServer: [
    {
      command: "uv run --project ../backend recsys serve --port 8010",
      url: "http://127.0.0.1:8010/api/health",
      // Never reuse: an already running dev backend (scripts\dev.ps1) serves data/app.db, and the tests would
      // write their profiles into it. Playwright stops with "already used" instead; stop the dev server first.
      reuseExistingServer: false,
      timeout: 120_000,
      env: { RECSYS_PATHS__DB_PATH: "data/e2e.db" },
      stdout: "pipe",
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
