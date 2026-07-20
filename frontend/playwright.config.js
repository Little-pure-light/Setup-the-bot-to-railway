import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 60_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    { name: 'Desktop Chrome', use: { ...devices['Desktop Chrome'] } },
    // 使用 Chromium + 裝置 viewport，避免本機未安裝 WebKit 導致失敗
    {
      name: 'iPhone 13',
      use: {
        ...devices['iPhone 13'],
        browserName: 'chromium',
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: 'Pixel 7',
      use: {
        ...devices['Pixel 7'],
        browserName: 'chromium',
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
})
