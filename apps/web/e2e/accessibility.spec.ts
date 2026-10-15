import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { mockStagecoachApi, SESSION_ID } from "./helpers.ts";

test("report page has no serious axe-core violations", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "Axe report talk" });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  const results = await new AxeBuilder({ page })
    .include('[data-testid="report"]')
    .disableRules(["color-contrast"])
    .analyze();
  const serious = results.violations.filter((row) => row.impact === "serious" || row.impact === "critical");
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});

test("keyboard-only: player, evidence, and timeline stay reachable", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "Keyboard report talk" });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("timeline")).toBeVisible();

  const player = page.getByLabel(/recording player/i);
  await player.focus();
  await expect(player).toBeFocused();
  await page.keyboard.press("Space");

  const evidence = page.getByRole("button", { name: /▶/ }).first();
  await evidence.focus();
  await expect(evidence).toBeFocused();
  await page.keyboard.press("Enter");

  const lane = page.getByTestId("timeline-lane-fillers");
  await lane.focus();
  await expect(lane).toBeFocused();
  await page.keyboard.press("Enter");
});

test("report video exposes captions from the transcript", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "Caption talk" });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("video track[kind='captions']")).toHaveCount(1);
});
