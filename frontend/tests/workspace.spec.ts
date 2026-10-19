import { test, expect } from "@playwright/test";

test("login, empty workspace, document upload and logout through the real API", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("ui@test.local");
  await page.getByLabel("Mot de passe").fill("browser-password-123");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(
    page.getByRole("heading", { name: "Une vue claire sur chaque événement." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Votre première analyse commence ici." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Procédures", exact: true }).click();
  await page.locator("input[type=file]").setInputFiles({
    name: "procedure.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Zone A : vérifier la vidéo avant de créer un ticket."),
  });
  await expect(page.getByText("procedure.txt", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Document enregistré. Consulte son état d’indexation."),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/workspace.png", fullPage: true });
  await page.getByRole("button", { name: "Déconnexion" }).click();
  await expect(
    page.getByRole("button", { name: "Se connecter" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
