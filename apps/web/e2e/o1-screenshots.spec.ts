import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdirSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { silentWav } from "./helpers.ts";
import { SESSION_ID, layoutFixture, mockOnlineApi } from "./online-helpers.ts";

const OUT = process.env.O1_SCREEN_DIR || "/opt/cursor/artifacts/o1-screens";
const WIDTHS = [390, 1440] as const;
const THEMES = ["dark", "light"] as const;

test.use({
  reducedMotion: "reduce",
});

async function snap(page: Page, name: string, width: number, theme: string) {
  mkdirSync(OUT, { recursive: true });
  if (width === 390) {
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(390);
  }
  await expect(page.locator(".animate-spin, [data-testid=session-skeleton], [data-testid=layout-loading]")).toHaveCount(0);
  await page.screenshot({
    path: `${OUT}/${name}_${width}_${theme}.png`,
    fullPage: true,
  });
}

async function themeAndWidth(page: Page, width: number, theme: string) {
  await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  await page.addInitScript((next) => {
    localStorage.setItem("cs-theme", next);
    document.documentElement.dataset.theme = next;
  }, theme);
}

async function waitReady(page: Page, locator: ReturnType<Page["getByTestId"]> | ReturnType<Page["getByRole"]>) {
  await expect(locator).toBeVisible({ timeout: 15_000 });
  await page.waitForLoadState("networkidle");
}

test.describe("O1 design screenshots", () => {
  for (const width of WIDTHS) {
    test.describe(`${width}px`, () => {
      test.use({ deviceScaleFactor: width === 390 ? 2 : 1 });

      for (const theme of THEMES) {
        test(`S1a empty ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page);
          await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByRole("heading", { name: /where did you present/i }));
          await snap(page, "s1a_empty", width, theme);
        });

        test(`S1a error ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page);
          await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
          await page.getByTestId("continue-mode").click();
          await waitReady(page, page.getByText(/choose/i));
          await snap(page, "s1a_error", width, theme);
        });

        test(`S1a success ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page);
          await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
          await page.getByTestId("mode-webinar").click();
          await expect(page.getByTestId("mode-webinar")).toHaveAttribute("aria-checked", "true");
          await snap(page, "s1a_success", width, theme);
        });

        test(`S1b empty ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page);
          await page.goto("/sessions/new?step=recording&mode=webinar", { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByRole("heading", { name: /add your recording/i }));
          await snap(page, "s1b_empty", width, theme);
        });

        test(`S1b success ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page);
          await page.goto("/sessions/new?step=recording&mode=webinar", { waitUntil: "domcontentloaded" });
          await page.getByTestId("session-file").setInputFiles({
            name: "q3-security-webinar.mp4",
            mimeType: "video/mp4",
            buffer: silentWav(),
          });
          await expect(page.getByText("q3-security-webinar.mp4")).toBeVisible();
          await snap(page, "s1b_success", width, theme);
        });

        test(`S1b long ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page);
          await page.goto("/sessions/new?step=recording&mode=webinar", { waitUntil: "domcontentloaded" });
          await page.getByTestId("session-file").setInputFiles({
            name: "q3-security-webinar-very-long-export-name.mp4",
            mimeType: "video/mp4",
            buffer: silentWav(),
          });
          await page.locator('input[name="title"]').fill("Q3 security webinar for the whole company and partners worldwide extra");
          await expect(page.getByText(/q3-security-webinar-very-long/i)).toBeVisible();
          await snap(page, "s1b_long", width, theme);
        });

        test(`S1b uploading ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { hangUpload: true });
          await page.goto("/sessions/new?step=recording&mode=webinar", { waitUntil: "domcontentloaded" });
          await page.getByTestId("session-file").setInputFiles({
            name: "q3-security-webinar.mp4",
            mimeType: "video/mp4",
            buffer: silentWav(2),
          });
          await page.getByLabel(/I recorded this session/i).check();
          await page.getByTestId("upload-continue").click();
          await expect(page.getByText(/uploading/i)).toBeVisible({ timeout: 10_000 });
          await snap(page, "s1b_loading", width, theme);
        });

        test(`S1b 413 ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, {
            uploadStatus: 413,
            uploadDetail: "This file is 2.4 GB. The limit is 2 GB. Trim it or export at 720p.",
          });
          await page.goto("/sessions/new?step=recording&mode=webinar", { waitUntil: "domcontentloaded" });
          await page.getByTestId("session-file").setInputFiles({
            name: "huge.mp4",
            mimeType: "video/mp4",
            buffer: silentWav(),
          });
          await page.getByLabel(/I recorded this session/i).check();
          await page.getByTestId("upload-continue").click();
          await expect(page.getByText(/file too large/i)).toBeVisible({ timeout: 10_000 });
          await expect(page.getByRole("button", { name: /try again/i })).toHaveCount(0);
          await snap(page, "s1b_error", width, theme);
        });

        test(`S2 preparing ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "preparing", startedAgo: 15 });
          await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("preparing"));
          await expect(page.getByTestId("report")).toHaveCount(0);
          await expect(page.getByTestId("export-pdf")).toHaveCount(0);
          await snap(page, "s2_success", width, theme);
        });

        test(`S2 still working ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await page.clock.install();
          const now = Date.now();
          await page.clock.setFixedTime(now);
          await mockOnlineApi(page, { status: "preparing", startedAgo: 75 });
          await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("preparing"));
          await expect(page.getByText(/still working/i)).toBeVisible();
          await snap(page, "s2_slow", width, theme);
        });

        test(`S2 error ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "failed" });
          await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("prepare-error"));
          await expect(page.getByTestId("upload-another")).toBeVisible();
          await expect(page.getByText(/couldn't prepare/i)).toBeVisible();
          await expect(page.getByText(/usually under a minute/i)).toHaveCount(0);
          await expect(page.getByTestId("stage-log")).toHaveCount(0);
          await snap(page, "s2_error", width, theme);
        });

        test(`S3 high ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
          await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("confidence-line"));
          await snap(page, "s3_high", width, theme);
        });

        test(`S3 check ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("check") });
          await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("confidence-line"));
          await snap(page, "s3_check", width, theme);
        });

        test(`S3 unsure ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("unsure") });
          await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("confidence-line"));
          await snap(page, "s3_unsure", width, theme);
        });

        test(`S3 empty ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("empty") });
          await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("layout-empty"));
          await snap(page, "s3_empty", width, theme);
        });

        test(`S3 camera ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("camera") });
          await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("confidence-line"));
          await snap(page, "s3_camera", width, theme);
        });

        test(`S3 screen ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("screen") });
          await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("confidence-line"));
          await snap(page, "s3_screen", width, theme);
        });

        test(`S3 auto ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          const layout = layoutFixture("high");
          layout.auto_confirmed = true;
          await mockOnlineApi(page, { layout, autoConfirmed: true, status: "layout_review" });
          await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("confidence-line"));
          await expect(page.getByText(/the layout we used/i)).toBeVisible();
          await expect(page.getByTestId("back-to-session")).toBeVisible();
          await expect(page.getByTestId("looks-right")).toHaveCount(0);
          await expect(page.getByTestId("analyse-audio")).toHaveCount(0);
          await snap(page, "s3_auto", width, theme);
        });

        test(`S3 consent off ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "processing", consentOff: true, startedAgo: 45 });
          await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("processing"));
          await expect(page.getByRole("link", { name: /open settings/i }).first()).toBeVisible();
          await expect(page.locator('[data-stage="layout"][data-status="skipped"]')).toBeVisible();
          await expect(page.getByText(/skipped · audio only/i).first()).toBeVisible();
          await snap(page, "s3_consent", width, theme);
        });

        test(`S4 processing ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "processing", startedAgo: 45 });
          await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("processing"));
          await expect(page.getByText(/measuring camera presence/i)).toBeVisible();
          await expect(page.getByText(/by you/i).first()).toBeVisible();
          await expect(page.getByText(/confirmed automatically/i)).toHaveCount(0);
          await expect(page.locator('[data-stage="layout_review"]')).toHaveAttribute("data-status", "succeeded");
          await expect(page.locator('[data-status="running"]')).toHaveCount(1);
          await snap(page, "s4_success", width, theme);
        });

        test(`S5 success ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "ready", success: true });
          await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("report"));
          await expect(page.getByText(/partial score/i)).toHaveCount(0);
          await snap(page, "s5_success", width, theme);
        });

        test(`S5 partial ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await mockOnlineApi(page, { status: "partial", coreNa: true });
          await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
          await waitReady(page, page.getByTestId("not-measured"));
          await snap(page, "s5_partial", width, theme);
        });
      }
    });
  }

  for (const width of WIDTHS) {
    test.describe(`pt-BR ${width}`, () => {
      test.use({ deviceScaleFactor: width === 390 ? 2 : 1 });

      test(`S1a empty pt-BR ${width} dark`, async ({ page }) => {
        await themeAndWidth(page, width, "dark");
        await mockOnlineApi(page, { locale: "pt-BR" });
        await page.goto("/pt-BR/sessions/new?step=where", { waitUntil: "domcontentloaded" });
        await waitReady(page, page.getByRole("heading"));
        await snap(page, "s1a_empty_pt-BR", width, "dark");
      });

      test(`S3 high pt-BR ${width} dark`, async ({ page }) => {
        await themeAndWidth(page, width, "dark");
        await mockOnlineApi(page, { locale: "pt-BR", status: "layout_review", layout: layoutFixture("high") });
        await page.goto(`/pt-BR/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await waitReady(page, page.getByTestId("confidence-line"));
        await snap(page, "s3_high_pt-BR", width, "dark");
      });

      test(`S5 success pt-BR ${width} dark`, async ({ page }) => {
        await themeAndWidth(page, width, "dark");
        await mockOnlineApi(page, { locale: "pt-BR", status: "ready", success: true });
        await page.goto(`/pt-BR/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
        await waitReady(page, page.getByTestId("report"));
        await snap(page, "s5_success_pt-BR", width, "dark");
      });

      test(`S3 check pt-BR ${width} dark`, async ({ page }) => {
        await themeAndWidth(page, width, "dark");
        await mockOnlineApi(page, { locale: "pt-BR", status: "layout_review", layout: layoutFixture("check") });
        await page.goto(`/pt-BR/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await waitReady(page, page.getByTestId("confidence-line"));
        await expect(page.getByText(/câmara|câmera/i).first()).toBeVisible();
        await snap(page, "s3_check_pt-BR", width, "dark");
      });

      test(`S4 processing pt-BR ${width} dark`, async ({ page }) => {
        await themeAndWidth(page, width, "dark");
        await mockOnlineApi(page, { locale: "pt-BR", status: "processing", startedAgo: 45 });
        await page.goto(`/pt-BR/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
        await waitReady(page, page.getByTestId("processing"));
        await snap(page, "s4_success_pt-BR", width, "dark");
      });
    });
  }

  test("screenshot set has no byte-identical duplicates", () => {
    const files = readdirSync(OUT).filter((name) => name.endsWith(".png"));
    const seen = new Map<string, string>();
    for (const file of files) {
      const hash = createHash("md5").update(readFileSync(join(OUT, file))).digest("hex");
      const previous = seen.get(hash);
      expect(previous, `duplicate screenshot ${file} == ${previous}`).toBeUndefined();
      seen.set(hash, file);
    }
  });
});
