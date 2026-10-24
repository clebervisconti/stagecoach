import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { SESSION_ID, layoutFixture, mockOnlineApi } from "./online-helpers.ts";

test("F2 adjust moves a box and analyses with that layout", async ({ page }) => {
  let saved: { segments?: { regions?: { id: string; x: number }[] }[] } | null = null;
  await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
  await page.route("**/api/stagecoach/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/stagecoach/, "");
    if (route.request().method() === "PUT" && path === `/sessions/${SESSION_ID}/layout`) {
      saved = route.request().postDataJSON();
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "processing", layout_version: 2, edit_count: 1 }),
      });
    }
    return route.fallback();
  });
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("adjust").click();
  const camera = page.getByTestId("region-r0");
  await expect(camera).toBeVisible();
  await camera.focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByTestId("analyse-layout")).toBeVisible();
  await page.getByTestId("analyse-layout").click();
  await expect(page).toHaveURL(new RegExp(`/sessions/${SESSION_ID}$`));
  const region = saved?.segments?.[0]?.regions?.find((row) => row.id === "r0");
  expect(region).toBeTruthy();
  expect(region!.x).toBeLessThan(0.8);
});

test("F6 change layout reopens the editor and saves without a new upload", async ({ page }) => {
  let reanalysed = 0;
  let saved = 0;
  await mockOnlineApi(page, { status: "ready", success: true });
  await page.route("**/api/stagecoach/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/stagecoach/, "");
    if (route.request().method() === "POST" && path === `/sessions/${SESSION_ID}/reanalyse-layout`) {
      reanalysed += 1;
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "layout_review", job_id: "job-2", layout_version: 1 }),
      });
    }
    if (route.request().method() === "PUT" && path === `/sessions/${SESSION_ID}/layout`) {
      saved += 1;
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "processing", layout_version: 2, edit_count: 0 }),
      });
    }
    return route.fallback();
  });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("report-menu").click();
  await page.getByTestId("change-layout").click();
  await expect(page).toHaveURL(new RegExp(`/sessions/${SESSION_ID}/layout\\?edit=1`));
  await expect(page.getByTestId("analyse-layout")).toBeVisible();
  await page.getByTestId("analyse-layout").click();
  await expect(page).toHaveURL(new RegExp(`/sessions/${SESSION_ID}$`));
  expect(reanalysed).toBe(1);
  expect(saved).toBe(1);
});

test("empty layout offers draw regions, and a conflict keeps the edit", async ({ page }) => {
  await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("empty") });
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("layout-empty")).toBeVisible();
  await expect(page.getByTestId("draw-regions")).toBeVisible();
  await expect(page.getByTestId("analyse-audio")).toBeVisible();
  await page.getByTestId("draw-regions").click();
  await expect(page.getByTestId("editing-badge")).toBeVisible();
});

test("save conflict keeps the local edit on screen", async ({ page }) => {
  await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
  await page.route("**/api/stagecoach/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/stagecoach/, "");
    if (route.request().method() === "PUT" && path === `/sessions/${SESSION_ID}/layout`) {
      return route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "layout version conflict" }) });
    }
    return route.fallback();
  });
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("adjust").click();
  await page.getByTestId("region-r0").focus();
  await page.keyboard.press("ArrowLeft");
  await page.getByTestId("analyse-layout").click();
  await expect(page.getByTestId("layout-save-error")).toBeVisible();
  await expect(page.getByTestId("region-r0")).toBeVisible();
  await expect(page.getByTestId("try-again")).toBeVisible();
  await expect(page.getByTestId("discard")).toBeVisible();
});

test("consent off uses a neutral layout check and still adjusts", async ({ page }) => {
  await mockOnlineApi(page, { status: "layout_review", consentOff: true, layout: layoutFixture("high") });
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/layout check/i).first()).toBeVisible();
  await expect(page.getByText(/we found your camera/i)).toHaveCount(0);
  await expect(page.getByTestId("adjust")).toBeVisible();
});

test("stepper steps 1 and 2 leave the session for the wizard", async ({ page }) => {
  await mockOnlineApi(page, { status: "layout_review" });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("stepper-where").click();
  await expect(page).toHaveURL(/step=where/);
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("stepper-recording").click();
  await expect(page).toHaveURL(/step=recording/);
});

test("playback error is inside the video box and the video is removed", async ({ page }) => {
  await mockOnlineApi(page, { status: "ready", success: true });
  await page.route("**/api/stagecoach/sessions/*/media**", async (route) => {
    if (route.request().url().includes("playback")) return route.fallback();
    return route.fulfill({ status: 404, body: "missing" });
  });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  const error = page.getByTestId("player-error");
  await expect(error).toBeVisible();
  await expect(page.locator("video")).toHaveCount(0);
  const box = await error.boundingBox();
  const frame = await page.locator(".aspect-video").first().boundingBox();
  expect(box && frame && box.y >= frame.y && box.y + box.height <= frame.y + frame.height + 1).toBeTruthy();
});

test("layout editor has no serious axe violations", async ({ page }) => {
  await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`/sessions/${SESSION_ID}/layout?edit=1`, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("editing-badge")).toBeVisible();
    const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
    const serious = results.violations.filter((row) => row.impact === "serious" || row.impact === "critical");
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  }
});
