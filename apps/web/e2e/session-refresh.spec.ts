import { expect, test } from "@playwright/test";
import { SESSION_ID, layoutFixture, mockOnlineApi, pastIso } from "./online-helpers.ts";

const ARTIFACT = /\/(report|transcript|timeline|body|slides|coaching|series|goals)(\/|$|\?)/;

test("processing does not fetch artifacts while events are still running", async ({ page }) => {
  const hits: string[] = [];
  page.on("request", (request) => {
    if (ARTIFACT.test(request.url())) hits.push(new URL(request.url()).pathname);
  });
  await mockOnlineApi(page, { status: "processing", startedAgo: 45 });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("processing")).toBeVisible();
  await page.waitForTimeout(400);
  expect(hits).toEqual([]);
});

test("a session load error clears after the next successful refresh", async ({ page }) => {
  test.setTimeout(30_000);
  await mockOnlineApi(page, { status: "processing", title: "Q3 security webinar" });
  let hits = 0;
  await page.route(`**/api/stagecoach/sessions/${SESSION_ID}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    hits += 1;
    if (hits === 1) {
      return route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
    }
    return route.fallback();
  });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  const alert = page.getByRole("alert").filter({ hasText: "Could not load this session." });
  await expect(alert).toBeVisible();
  await expect(page.getByRole("heading", { name: "Q3 security webinar" })).toHaveCount(0);
  await expect.poll(() => hits, { timeout: 20_000 }).toBeGreaterThanOrEqual(2);
  await expect(alert).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Q3 security webinar" })).toBeVisible();
});

test("a 429 backs off using retry-after", async ({ page }) => {
  test.setTimeout(20_000);
  await mockOnlineApi(page, { status: "processing" });
  let hits = 0;
  await page.route(`**/api/stagecoach/sessions/${SESSION_ID}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    hits += 1;
    if (hits === 1) {
      return route.fulfill({
        status: 429,
        contentType: "application/problem+json",
        headers: { "retry-after": "1" },
        body: JSON.stringify({ title: "Too Many Requests", status: 429 }),
      });
    }
    return route.fallback();
  });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.waitForResponse((response) => response.status() === 429);
  await expect(page.getByTestId("session-skeleton")).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Could not load this session." })).toHaveCount(0);
  await page.waitForTimeout(400);
  expect(hits).toBe(1);
  await expect.poll(() => hits, { timeout: 5_000 }).toBe(2);
  await expect(page.getByTestId("processing")).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Could not load this session." })).toHaveCount(0);
});

test("preparing shows the current sub-step, the elapsed time, and a poster placeholder", async ({ page }) => {
  await mockOnlineApi(page, {
    status: "preparing",
    liveIngest: "ingest_audio",
    startedAgo: 90,
    posterReady: false,
    title: "Q3 security webinar",
  });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("prep-activity")).toHaveText("Extracting audio");
  await expect(page.getByTestId("elapsed")).not.toHaveText("0:00");
  await expect(page.getByText(/9:00/)).toBeVisible();
  await expect(page.getByTestId("poster-placeholder")).toBeVisible();
  await expect(page.getByTestId("session-poster")).toHaveCount(0);
  expect(pastIso(90).endsWith("Z")).toBe(true);
});

test("the layout headline follows segments that are not the opening composition", async ({ page }) => {
  const screen = layoutFixture("screen");
  const camera = layoutFixture("camera");
  const both = layoutFixture("high");
  const layout = layoutFixture("high");
  layout.confidence = 0.92;
  layout.review_reason = null;
  layout.segments = [
    { ...screen.segments[0], index: 0, t_start: 0, t_end: 20, confidence: 0.92 },
    { ...camera.segments[0], index: 1, t_start: 20, t_end: 400, confidence: 0.92 },
    { ...both.segments[0], index: 2, t_start: 400, t_end: 540, confidence: 0.92 },
  ];
  await mockOnlineApi(page, { status: "layout_review", layout });
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  const line = page.getByTestId("confidence-line");
  await expect(line).toBeVisible();
  await expect(line).not.toContainText(/isn't visible/i);
  await expect(line).toContainText(/segments/i);
  await expect(line).toContainText(/camera only/i);
});
