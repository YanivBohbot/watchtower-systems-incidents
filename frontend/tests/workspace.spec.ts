import { test, expect } from "@playwright/test";

test("login, empty workspace, document upload and logout through the real API", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Email address").fill("ui@test.local");
  await page.getByLabel("Password").fill("browser-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Video analysis" }).click();
  await expect(
    page.getByRole("heading", { name: "A clear view of every event." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Your first analysis starts here." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Procedures", exact: true }).click();
  await page.locator("input[type=file]").setInputFiles({
    name: "procedure.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Zone A: check the video before creating a ticket."),
  });
  await expect(page.getByText("procedure.txt", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Document saved. Check its indexing status."),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/workspace.png", fullPage: true });
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("button", { name: "Sign in" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
