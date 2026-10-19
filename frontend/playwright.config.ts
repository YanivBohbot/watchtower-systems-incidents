import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://127.0.0.1:5174", headless: true },
  webServer: [
    {
      command: `${process.env.WATCHTOWER_PYTHON || "python"} -m uvicorn ui_server:build_app --factory --app-dir ../backend/tests --host 127.0.0.1 --port 8011`,
      env: { PYTHONPATH: "../backend" },
      url: "http://127.0.0.1:8011/api/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 5174",
      env: { API_PROXY_TARGET: "http://127.0.0.1:8011" },
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
    },
  ],
});
