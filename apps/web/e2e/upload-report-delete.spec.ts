import { expect, test } from "@playwright/test";
import { mockStagecoachApi, SESSION_ID, silentWav } from "./helpers.ts";

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

test("print view visual snapshot matches the web report", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await mockStagecoachApi(page, { language: "en", title: "PDF snapshot talk" });
  await page.goto("/sessions", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("new-session")).toBeVisible();
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  const webScore = await page.locator("#report-summary-heading").innerText();
  await expect(page.getByTestId("export-pdf")).toBeVisible();
  await page.goto(`/sessions/${SESSION_ID}/print`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("pdf-print")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("#report-summary-heading")).toHaveText(webScore);
  await expect(page.getByTestId("pdf-transcript")).toHaveCount(0);
  await expect(page.locator("#report-summary-heading")).toHaveScreenshot("report-print-score.png", {
    maxDiffPixels: 80,
    animations: "disabled",
  });
});

test("body and slides tabs render from report artifacts", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "Body slides talk" });
  await page.goto("/sessions", { waitUntil: "domcontentloaded" });
  await uploadTalk(page, "Body slides talk", "en");
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("tab", { name: /^body$/i }).click();
  await expect(page.getByTestId("body-tab")).toBeVisible();
  await expect(page.getByTestId("data-quality")).toBeVisible();
  await page.getByRole("tab", { name: /^slides$/i }).click();
  await expect(page.getByTestId("slides-tab")).toBeVisible();
  await expect(page.getByTestId("slide-card")).toBeVisible();
  await expect(page.getByTestId("ai-suggestion")).toContainText(/AI suggestion/i);
});

test("references, myths, and scoring-config pages render", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "References talk" });
  await page.goto("/research", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("references-page")).toBeVisible();
  await expect(page.locator("#S20")).toBeVisible();
  await page.goto("/research/myths", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("myths-page")).toBeVisible();
  await expect(page.getByText(/7-38-55/i)).toBeVisible();
  await page.goto("/config/scoring/1.0.0", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("scoring-config-page")).toBeVisible();
  await expect(page.getByTestId("scoring-config-yaml")).toContainText("version:");
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
