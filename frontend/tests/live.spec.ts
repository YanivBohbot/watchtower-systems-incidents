import { test, expect } from "@playwright/test";

test("camera wall shows the live tile and a pushed alert without reloading", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Email address").fill("ui@test.local");
  await page.getByLabel("Password").fill("browser-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Every camera at a glance." }),
  ).toBeVisible({ timeout: 20_000 }); // password hashing is slow on small CPUs
  await expect(page.getByAltText("Live view of hall")).toBeVisible();
  await expect(page.getByText("1,200 frames analyzed")).toBeVisible();
  await expect(page.getByText("LIVE", { exact: true })).toBeVisible();

  const response = await request.post("/api/test/alert");
  expect(response.ok()).toBeTruthy();

  const banner = page.locator(".alert-banner");
  await expect(banner).toContainText("Alert · hall");
  await expect(banner).toContainText("Person in restricted zone · 91%");
  await expect(page.getByLabel("Camera hall")).toHaveClass(/alerting/);
  await page.screenshot({ path: "test-results/live.png", fullPage: true });
  await page.getByRole("button", { name: "Dismiss alert" }).click();
  await expect(banner).toHaveCount(0);
  expect(errors).toEqual([]);
});
