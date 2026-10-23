import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { SESSION_ID, layoutFixture, mockOnlineApi } from "./online-helpers.ts";
import type { LayoutView } from "../lib/online.ts";

const OUT = process.env.O2_SCREEN_DIR || (process.env.CI ? "test-results/o2-screens" : "/opt/cursor/artifacts/o2-screens");
const WIDTHS = [390, 1440] as const;
const THEMES = ["dark", "light"] as const;

test.use({ reducedMotion: "reduce" });

async function themeAndWidth(page: Page, width: number, theme: string) {
  await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  await page.addInitScript((next) => {
    localStorage.setItem("cs-theme", next);
    document.documentElement.dataset.theme = next;
  }, theme);
}

async function snap(page: Page, name: string, width: number, theme: string, keepLoading = false) {
  mkdirSync(OUT, { recursive: true });
  if (width === 390) {
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(390);
  }
  if (!keepLoading) {
    await expect(page.locator("[data-testid=session-skeleton], [data-testid=layout-loading]")).toHaveCount(0);
  }
  await page.screenshot({ path: `${OUT}/${name}_${width}_${theme}.png`, fullPage: true });
}

function longLayout(): LayoutView {
  const base = layoutFixture("high");
  const preview = base.segments[0]?.preview_url;
  base.frame = { width: 1920, height: 1080, duration_s: 540 };
  base.segments = Array.from({ length: 9 }, (_, index) => ({
    index,
    t_start: index * 60,
    t_end: (index + 1) * 60,
    kind: "composite",
    confidence: 0.8,
    preview_url: preview,
    regions: [
      { id: `c${index}`, role: "camera", x: 0.72, y: 0.04, w: 0.22, h: 0.28, confidence: 0.9 },
      { id: `s${index}`, role: "screen", x: 0.04, y: 0.04, w: 0.64, h: 0.62, confidence: 0.88 },
      { id: `o${index}`, role: "other_participant", x: 0.72, y: 0.36, w: 0.22, h: 0.24, confidence: 0.7 },
      { id: `i${index}`, role: "ignore", x: 0.04, y: 0.7, w: 0.28, h: 0.22, confidence: 0.6 },
      { id: `j${index}`, role: "ignore", x: 0.36, y: 0.7, w: 0.28, h: 0.22, confidence: 0.6 },
      { id: `k${index}`, role: "ignore", x: 0.68, y: 0.7, w: 0.26, h: 0.22, confidence: 0.6 },
    ],
  }));
  return base;
}

test("O2 layout screens at 390 and 1440, light and dark", async ({ page }) => {
  test.setTimeout(180_000);
  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      await themeAndWidth(page, width, theme);
      await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
      await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("looks-right")).toBeVisible();
      await snap(page, "review", width, theme);

      await page.getByTestId("adjust").click();
      await expect(page.getByTestId("editing-badge")).toBeVisible();
      await snap(page, "edit-clean", width, theme);
      await page.getByTestId("region-r0").focus();
      await page.keyboard.press("ArrowLeft");
      await expect(page.getByTestId("unsaved-changes")).toBeVisible();
      await snap(page, "edit-dirty", width, theme);

      await themeAndWidth(page, width, theme);
      await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("empty") });
      await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("layout-empty")).toBeVisible();
      await snap(page, "empty", width, theme);
      await page.getByTestId("draw-regions").click();
      await snap(page, "drawing", width, theme);

      const trimmed = layoutFixture("high");
      trimmed.analysis_window = { start_s: 60, end_s: 480 };
      await themeAndWidth(page, width, theme);
      await mockOnlineApi(page, { status: "layout_review", layout: trimmed });
      await page.goto(`/sessions/${SESSION_ID}/layout?edit=1`, { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("analysis-window")).toBeVisible();
      await snap(page, "trim", width, theme);

      await themeAndWidth(page, width, theme);
      await mockOnlineApi(page, { status: "layout_review", layout: longLayout() });
      await page.goto(`/sessions/${SESSION_ID}/layout?edit=1`, { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("segment-editor")).toBeVisible();
      await snap(page, "long", width, theme);

      await themeAndWidth(page, width, theme);
      await mockOnlineApi(page, { status: "layout_review", consentOff: true, layout: layoutFixture("screen") });
      await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
      await expect(page.getByText(/layout check|checagem de layout/i).first()).toBeVisible();
      await snap(page, "consent-off", width, theme);
    }
  }
});

test("O2 loading, save error, and report menu", async ({ page }) => {
  test.setTimeout(180_000);
  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      await themeAndWidth(page, width, theme);
      await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
      await page.route("**/api/stagecoach/sessions/*/layout", async (route) => {
        if (route.request().method() !== "GET") return route.fallback();
        await new Promise((resolve) => setTimeout(resolve, 8000));
        return route.fallback();
      });
      await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("layout-loading")).toBeVisible();
      await snap(page, "loading", width, theme, true);
      await page.unroute("**/api/stagecoach/sessions/*/layout");
      await expect(page.getByTestId("looks-right")).toBeVisible({ timeout: 15_000 });

      await page.route("**/api/stagecoach/**", async (route) => {
        const path = new URL(route.request().url()).pathname.replace(/^\/api\/stagecoach/, "");
        if (route.request().method() === "PUT" && path === `/sessions/${SESSION_ID}/layout`) {
          return route.fulfill({ status: 409, contentType: "application/json", body: "{}" });
        }
        return route.fallback();
      });
      await page.getByTestId("adjust").click();
      await page.getByTestId("region-r0").focus();
      await page.keyboard.press("ArrowLeft");
      await page.getByTestId("analyse-layout").click();
      await expect(page.getByTestId("layout-save-error")).toBeVisible();
      await snap(page, "save-error", width, theme);

      await themeAndWidth(page, width, theme);
      await mockOnlineApi(page, { status: "ready", success: true, title: "Q3 security webinar" });
      await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
      await page.getByTestId("report-menu").click();
      await expect(page.getByTestId("change-layout")).toBeVisible();
      await snap(page, "f6-menu", width, theme);
    }
  }
});
