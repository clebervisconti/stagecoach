import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { silentWav } from "./helpers.ts";
import { SESSION_ID, layoutFixture, mockOnlineApi } from "./online-helpers.ts";

const OUT = process.env.O1_SCREEN_DIR || "/opt/cursor/artifacts/o1-screens";
const WIDTHS = [390, 1440] as const;
const THEMES = ["dark", "light"] as const;

async function snap(page: Page, name: string, width: number, theme: string) {
  mkdirSync(OUT, { recursive: true });
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

test.describe("O1 design screenshots", () => {
  for (const width of WIDTHS) {
    for (const theme of THEMES) {
      test(`S1a empty ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page);
        await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
        await expect(page.getByRole("heading", { name: /where did you present/i })).toBeVisible();
        await snap(page, "s1a_empty", width, theme);
      });

      test(`S1a error ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page);
        await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
        await page.getByTestId("continue-mode").click();
        await expect(page.getByText(/choose/i)).toBeVisible();
        await snap(page, "s1a_error", width, theme);
      });

      test(`S1a success ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page);
        await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
        await page.getByTestId("mode-webinar").click();
        await snap(page, "s1a_success", width, theme);
      });

      test(`S1b empty ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page);
        await page.goto("/sessions/new?step=recording&mode=webinar", { waitUntil: "domcontentloaded" });
        await expect(page.getByRole("heading", { name: /add your recording/i })).toBeVisible();
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
        await mockOnlineApi(page, { uploadStatus: 413, uploadDetail: "This file is larger than 2 GB. Trim it or export at 720p." });
        await page.goto("/sessions/new?step=recording&mode=webinar", { waitUntil: "domcontentloaded" });
        await page.getByTestId("session-file").setInputFiles({
          name: "huge.mp4",
          mimeType: "video/mp4",
          buffer: silentWav(),
        });
        await page.getByLabel(/I recorded this session/i).check();
        await page.getByTestId("upload-continue").click();
        await expect(page.getByText(/2 GB/i)).toBeVisible({ timeout: 10_000 });
        await snap(page, "s1b_error", width, theme);
      });

      test(`S2 preparing ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { status: "preparing" });
        await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
        await expect(page.getByTestId("preparing")).toBeVisible();
        await snap(page, "s2_success", width, theme);
      });

      test(`S2 error ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { status: "failed" });
        await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
        await snap(page, "s2_error", width, theme);
      });

      test(`S3 high ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { layout: layoutFixture("high") });
        await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await expect(page.getByTestId("confidence-line")).toBeVisible();
        await snap(page, "s3_high", width, theme);
      });

      test(`S3 check ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { layout: layoutFixture("check") });
        await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await snap(page, "s3_check", width, theme);
      });

      test(`S3 unsure ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { layout: layoutFixture("unsure") });
        await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await snap(page, "s3_unsure", width, theme);
      });

      test(`S3 empty ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { layout: layoutFixture("empty") });
        await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await expect(page.getByTestId("layout-empty")).toBeVisible();
        await snap(page, "s3_empty", width, theme);
      });

      test(`S3 camera ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { layout: layoutFixture("camera") });
        await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await snap(page, "s3_camera", width, theme);
      });

      test(`S3 screen ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { layout: layoutFixture("screen") });
        await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
        await snap(page, "s3_screen", width, theme);
      });

      test(`S4 processing ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { status: "processing" });
        await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
        await expect(page.getByTestId("processing")).toBeVisible({ timeout: 15_000 });
        await snap(page, "s4_success", width, theme);
      });

      test(`S5 success ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { status: "partial" });
        await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
        await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
        await snap(page, "s5_success", width, theme);
      });

      test(`S5 partial ${width} ${theme}`, async ({ page }) => {
        await themeAndWidth(page, width, theme);
        await mockOnlineApi(page, { status: "partial", coreNa: true });
        await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
        await expect(page.getByTestId("not-measured")).toBeVisible({ timeout: 15_000 });
        await snap(page, "s5_partial", width, theme);
      });
    }
  }
});
