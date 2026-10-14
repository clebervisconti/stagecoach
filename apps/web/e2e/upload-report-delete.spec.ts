import { expect, test } from "@playwright/test";
import { mockStagecoachApi, silentWav } from "./helpers.ts";

async function uploadTalk(
  page: import("@playwright/test").Page,
  title: string,
  language: "en" | "pt-BR",
) {
  await page.getByTestId("new-session").click();
  await expect(page.getByTestId("consent-panel")).toBeVisible();
  await expect(page.getByTestId("consent-video_analysis")).toBeVisible();
  await page.locator('input[name="title"]').fill(title);
  await page.locator('select[name="language"]').selectOption(language);
  await page.getByTestId("session-file").setInputFiles({
    name: language.startsWith("pt") ? "fala.wav" : "talk.wav",
    mimeType: "audio/wav",
    buffer: silentWav(),
  });
  await page.locator('form[data-testid="session-form"] button').click();
}

test("upload → progress → report → delete (en)", async ({ page }) => {
  const api = await mockStagecoachApi(page, { language: "en", title: "Phase 1 exit talk" });
  await page.goto("/sessions", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("new-session")).toBeVisible();
  await expect(page.getByTestId("empty-sessions")).toBeVisible();
  await uploadTalk(page, "Phase 1 exit talk", "en");
  await expect(page).toHaveURL(/\/sessions\/11111111-1111-4111-8111-111111111136/);
  await expect(page.getByTestId("processing")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("timeline")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("delete-session").click();
  await expect(page).toHaveURL(/\/sessions\/?$/);
  await expect(page.getByTestId("empty-sessions")).toBeVisible();
  expect(api.deleted()).toBe(true);
});

test("partial_ready shows the report while analysis is still processing", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "Live partial talk", stayProcessing: true });
  await page.goto("/sessions", { waitUntil: "domcontentloaded" });
  await uploadTalk(page, "Live partial talk", "en");
  await expect(page.getByTestId("processing")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("processing")).toBeVisible();
  await expect(page.getByText(/audio and text categories appear first/i)).toBeVisible();
});

test("pt-BR upload shows né/tipo/então disambiguation then delete", async ({ page }) => {
  const api = await mockStagecoachApi(page, { language: "pt-BR", title: "Fala de saída" });
  await page.goto("/pt-BR/sessions", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("new-session")).toBeVisible();
  await uploadTalk(page, "Fala de saída", "pt-BR");
  await expect(page.getByTestId("processing")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("tab", { name: /transcri/i }).click();
  await expect(page.getByTestId("fluency-disambig")).toBeVisible();
  await expect(page.locator('[data-testid="disambig-row"][data-word="né"]')).toContainText(/preenchimento|filler/i);
  await expect(page.locator('[data-testid="disambig-row"][data-word="tipo"]')).toContainText(/preenchimento|filler/i);
  await expect(page.locator('[data-testid="disambig-row"][data-word="então"]')).toContainText(/lexical/i);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("delete-session").click();
  await expect(page.getByTestId("empty-sessions")).toBeVisible();
  expect(api.deleted()).toBe(true);
});
