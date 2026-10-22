import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { silentWav } from "./helpers.ts";
import { SESSION_ID, layoutFixture, mockOnlineApi } from "./online-helpers.ts";

test("wizard: four mode cards, no tab bar, rights for webinar", async ({ page }) => {
  await mockOnlineApi(page);
  await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /where did you present/i })).toBeVisible();
  await expect(page.getByTestId("mode-stage")).toBeVisible();
  await expect(page.getByTestId("mode-webinar")).toBeVisible();
  await expect(page.getByTestId("mode-online_talk")).toBeVisible();
  await expect(page.getByTestId("mode-recorded_video")).toBeVisible();
  await page.getByTestId("continue-mode").click();
  await expect(page.getByText(/choose/i)).toBeVisible();
  await page.getByTestId("mode-webinar").click();
  await page.getByTestId("continue-mode").click();
  await expect(page.getByRole("heading", { name: /add your recording/i })).toBeVisible();
  await expect(page.getByRole("tablist")).toHaveCount(0);
  await expect(page.getByText(/other participants' faces are not analysed/i)).toBeVisible();
  await page.getByTestId("session-file").setInputFiles({
    name: "q3-security-webinar.mp4",
    mimeType: "video/mp4",
    buffer: silentWav(),
  });
  await expect(page.locator('input[name="title"]')).toHaveValue(/security webinar/i);
  await page.getByLabel(/I recorded this session/i).check();
  await page.getByTestId("upload-continue").click();
  await expect(page).toHaveURL(new RegExp(`/sessions/${SESSION_ID}`));
});

test("layout review: looks right and analyse audio only, no adjust", async ({ page }) => {
  await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /camera and your screen/i })).toBeVisible();
  await expect(page.getByTestId("confidence-line")).toContainText(/high confidence/i);
  await expect(page.getByTestId("looks-right")).toBeVisible();
  await expect(page.getByTestId("analyse-audio")).toBeVisible();
  await expect(page.getByRole("button", { name: /^adjust$/i })).toHaveCount(0);
  await page.getByTestId("looks-right").click();
  await expect(page).toHaveURL(new RegExp(`/sessions/${SESSION_ID}`));
});

test("scenario 17: layout review has no serious axe violations at 390 and 1440", async ({ page }) => {
  await mockOnlineApi(page, { layout: layoutFixture("high") });
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: /camera and your screen/i })).toBeVisible();
    const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
    const serious = results.violations.filter((row) => row.impact === "serious" || row.impact === "critical");
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  }
});

test("report hides body tab and shows not measured for online", async ({ page }) => {
  await mockOnlineApi(page, { status: "partial" });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("not-measured")).toBeVisible();
  await expect(page.getByRole("tab", { name: /^body$/i })).toHaveCount(0);
  await expect(page.getByRole("tab", { name: /on camera/i })).toHaveCount(0);
  await expect(page.getByRole("tab", { name: /^slides$/i })).toBeVisible();
  await expect(page.getByTestId("not-measured").getByText(/open settings/i)).toBeVisible();
});
