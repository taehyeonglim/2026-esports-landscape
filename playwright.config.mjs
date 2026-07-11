import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/browser.e2e.mjs",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4177",
    headless: true,
    locale: "ko-KR",
  },
  projects: [
    { name: "desktop-chromium", use: { browserName: "chromium", viewport: { width: 1440, height: 900 } } },
    { name: "desktop-firefox", use: { browserName: "firefox", viewport: { width: 1440, height: 900 } } },
    { name: "desktop-webkit", use: { browserName: "webkit", viewport: { width: 1440, height: 900 } } },
    { name: "android-chromium", use: { ...devices["Pixel 7"], browserName: "chromium" } },
    { name: "ios-webkit", use: { ...devices["iPhone 13"], browserName: "webkit" } },
  ],
  webServer: {
    command: "python3 -m http.server 4177 --directory dist",
    url: "http://127.0.0.1:4177/index.html",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
