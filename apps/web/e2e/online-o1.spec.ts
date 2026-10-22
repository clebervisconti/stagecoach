import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { silentWav } from "./helpers.ts";
import { SESSION_ID, layoutFixture, mockOnlineApi } from "./online-helpers.ts";

async function expectNoAxe(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((row) => row.impact === "serious" || row.impact === "critical");
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
}

async function expectNoOverflow(page: import("@playwright/test").Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
}

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
  await expect(page.getByTestId("not-measured").getByText(/open settings/i).first()).toBeVisible();
});

async function tabUntil(page: import("@playwright/test").Page, testId: string, limit = 24) {
  let current = "";
  for (let i = 0; i < limit; i += 1) {
    await page.keyboard.press("Tab");
    current = await page.evaluate(() => document.activeElement?.getAttribute("data-testid") ?? "");
    if (current === testId) return current;
  }
  return current;
}

test("keyboard-only walkthrough: mode, recording, layout", async ({ page }) => {
  await mockOnlineApi(page, { status: "layout_review", layout: layoutFixture("high") });
  await page.goto("/sessions/new?step=where", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /where did you present/i })).toBeVisible();
  const firstMode = await tabUntil(page, "mode-stage");
  expect(firstMode).toBe("mode-stage");
  await page.keyboard.press("Space");
  await expect(page.getByTestId("mode-stage")).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("mode-webinar")).toHaveAttribute("aria-checked", "true");
  expect(await tabUntil(page, "continue-mode")).toBe("continue-mode");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: /add your recording/i })).toBeVisible();
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("confidence-line")).toBeVisible();
  expect(await tabUntil(page, "looks-right")).toBe("looks-right");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/sessions/${SESSION_ID}`));
});

test("auto-confirmed layout is read-only", async ({ page }) => {
  const layout = layoutFixture("high");
  layout.auto_confirmed = true;
  await mockOnlineApi(page, { layout, autoConfirmed: true, status: "processing" });
  await page.goto(`/sessions/${SESSION_ID}/layout`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /the layout we used/i })).toBeVisible();
  await expect(page.getByTestId("back-to-session")).toBeVisible();
  await expect(page.getByTestId("looks-right")).toHaveCount(0);
  await expect(page.getByTestId("analyse-audio")).toHaveCount(0);
});

test("consent-off skips camera steps and links to settings", async ({ page }) => {
  await mockOnlineApi(page, { status: "processing", consentOff: true, startedAgo: 45 });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("link", { name: /open settings/i }).first()).toBeVisible();
  await expect(page.locator('[data-stage="layout"][data-status="skipped"]')).toBeVisible();
  await expect(page.getByText(/skipped · audio only/i).first()).toBeVisible();
});

test("S4 user-confirmed layout says by you", async ({ page }) => {
  await mockOnlineApi(page, { status: "processing", startedAgo: 45 });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/by you/i).first()).toBeVisible();
  await expect(page.getByText(/confirmed automatically/i)).toHaveCount(0);
});

test("reduced motion keeps the preparing scan line still", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockOnlineApi(page, { status: "preparing" });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("preparing")).toBeVisible();
  const duration = await page.locator(".cs-scan-line").first().evaluate((el) => getComputedStyle(el).animationDuration);
  expect(parseFloat(duration) || 0).toBeLessThan(0.05);
});

const O1_SCREENS = [
  { name: "S1a", path: "/sessions/new?step=where", ready: (page: import("@playwright/test").Page) => page.getByRole("heading", { name: /where did you present/i }) },
  { name: "S1b", path: "/sessions/new?step=recording&mode=webinar", ready: (page: import("@playwright/test").Page) => page.getByRole("heading", { name: /add your recording/i }) },
  { name: "S2", path: `/sessions/${SESSION_ID}`, status: "preparing" as const, ready: (page: import("@playwright/test").Page) => page.getByTestId("preparing") },
  { name: "S3", path: `/sessions/${SESSION_ID}/layout`, ready: (page: import("@playwright/test").Page) => page.getByTestId("confidence-line") },
  { name: "S4", path: `/sessions/${SESSION_ID}`, status: "processing" as const, ready: (page: import("@playwright/test").Page) => page.getByTestId("processing") },
  { name: "S5", path: `/sessions/${SESSION_ID}`, status: "ready" as const, success: true, ready: (page: import("@playwright/test").Page) => page.getByTestId("report") },
];

for (const screen of O1_SCREENS) {
  test(`axe 0 serious/critical on ${screen.name} at 390 and 1440`, async ({ page }) => {
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 844 });
      await mockOnlineApi(page, { status: screen.status ?? "preparing", success: screen.success });
      await page.goto(screen.path, { waitUntil: "domcontentloaded" });
      await expect(screen.ready(page)).toBeVisible({ timeout: 15_000 });
      await expectNoAxe(page);
      if (width === 390) await expectNoOverflow(page);
    }
  });
}
