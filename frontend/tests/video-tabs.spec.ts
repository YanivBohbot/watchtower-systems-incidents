import { test, expect } from "@playwright/test";

test("the selected video is downloaded once and kept across tab switches", async ({
  page,
}) => {
  const downloads: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/videos\/[^/]+\/content$/.test(request.url()))
      downloads.push(request.url());
  });
  await page.goto("/");
  await page.getByLabel("Email address").fill("ui@test.local");
  await page.getByLabel("Password").fill("browser-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Video analysis" }).click();
  await page
    .locator("input[type=file][accept^=video]")
    .setInputFiles({
      name: "tab-switch.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("not a real video"),
    });
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(
    page.getByText("Video saved. Processing has started in the background."),
  ).toBeVisible();
  await expect(page.locator(".video-stage video")).toBeVisible();
  await expect.poll(() => downloads.length).toBe(1);

  await page.getByRole("button", { name: "Procedures", exact: true }).click();
  await page.getByRole("button", { name: "Video analysis" }).click();
  await expect(page.locator(".video-stage video")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Your first analysis starts here." }),
  ).toHaveCount(0);
  await page.waitForTimeout(500);
  expect(downloads).toHaveLength(1);
});
