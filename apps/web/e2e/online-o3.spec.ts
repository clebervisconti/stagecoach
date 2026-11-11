import { mkdirSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { SESSION_ID, mockOnlineApi } from "./online-helpers.ts";

async function shot(page: Page, name: string) {
  if (!process.env.O3_SCREENSHOTS) return;
  const dir = "/opt/cursor/artifacts/screenshots";
  mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: `${dir}/${name}.png`, fullPage: true });
}

function documentFor(count: number, coachingFallback = false) {
  const segments = Array.from({ length: count }, (_, index) => ({
    id: `scr_${String(index + 1).padStart(3, "0")}`,
    index: index + 1,
    t_start: index * 12,
    t_end: index * 12 + 10,
    dwell_s: 10,
    type: index % 4 === 0 ? "DEMO" : "SLIDE",
    ocr_word_count: 20,
    flags:
      index % 11 === 0
        ? ["rushed"]
        : index % 13 === 0
          ? ["silent_demo"]
          : index % 17 === 0
            ? ["talk_over_transition"]
            : index % 19 === 0
              ? ["static_long"]
              : [],
    narration: {
      aligned: index % 2 === 0,
      shared_terms: index % 2 === 0 ? ["policy", "gateway"] : [],
    },
  }));
  return {
    delivery_mode: "webinar",
    screen_visible_s: count * 10,
    duration_s: Math.max(540, count * 12),
    segments,
    events: [
      { id: "ev_1", kind: "dead_air", t: 14, dur_s: 6 },
      { id: "ev_2", kind: "silent_demo", t: 40, dur_s: 18 },
      { id: "ev_3", kind: "talk_over", t: 22, dur_s: 1 },
      { id: "ev_4", kind: "interaction_prompt", t: 30, dur_s: 0 },
    ],
    metrics: [
      { id: "sf_clean_transition_ratio", value: 0.6, applicable: true },
      { id: "sf_narration_alignment_ratio", value: 0.8, applicable: true },
      { id: "sf_narration_lead_s_median", value: 3, applicable: true },
      { id: "sf_dead_air_per_10min", value: 3, applicable: true },
      { id: "sf_signpost_ratio", value: 0.5, applicable: true },
    ],
    coaching: {
      source: coachingFallback ? "template" : "online_flow_v1",
      fallback: coachingFallback,
      observations: [
        { title: coachingFallback ? "Metric: sf_clean_transition_ratio 0.6" : "Pause at the cut", detail: "Four cuts start mid-word.", t: 12, evidence_ids: ["scr_001"] },
        { title: "Name the next screen", detail: "Two changes have no lead-in.", t: 20, evidence_ids: ["scr_002"] },
        { title: "Ask once", detail: "The opening has no question.", t: 8, evidence_ids: ["ev_4"] },
      ],
      drills: [
        { title: "Pause", how: "Stop for a beat at each change.", practice_time_min: 10, targets_metric: "sf_clean_transition_ratio" },
        { title: "Signpost", how: "Say what the next screen is for.", practice_time_min: 10, targets_metric: "sf_signpost_ratio" },
        { title: "Ask", how: "Add one question in the opening.", practice_time_min: 10, targets_metric: "oe_interaction_prompts_per_10min" },
      ],
      strengths: [{ title: "You kept a screen visible.", evidence_ids: ["scr_001"] }],
    },
  };
}

async function fulfillScreens(page: Page, status: number, body: unknown) {
  await page.route(`**/api/stagecoach/sessions/${SESSION_ID}/screens`, async (route) => {
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

test("screen and flow: filters, seek, coaching footer, virtual list", async ({ page }) => {
  await mockOnlineApi(page, { status: "ready", success: true });
  await fulfillScreens(page, 200, documentFor(24));
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: /screen & flow/i }).click();
  await expect(page.getByTestId("screen-flow-ready")).toBeVisible();
  await expect(page.getByText("We coach how you present: timing, flow and how your words follow the screen. We never judge whether your content is correct.")).toBeVisible();
  await shot(page, "screen-flow-populated");
  await page.getByTestId("screen-row").first().getByRole("button").first().click();
  await expect(page.getByText(/not whether it was right/i)).toBeVisible();
  await expect(page.getByText(/incorrect/i)).toHaveCount(0);
  await page.getByRole("button", { name: /^Rushed/ }).click();
  await expect(page.getByRole("status")).toContainText(/of/i);
  const block = page.getByTestId("flow-block").first();
  await block.click();
  await expect(block).toHaveAttribute("aria-pressed", "true");
});

test("300 screens keep at most 30 rows in the document", async ({ page }) => {
  await mockOnlineApi(page, { status: "ready", success: true });
  await fulfillScreens(page, 200, documentFor(300));
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: /screen & flow/i }).click();
  await expect(page.getByTestId("screen-list")).toBeVisible();
  const rows = await page.getByTestId("screen-row").count();
  expect(rows).toBeLessThanOrEqual(30);
  expect(rows).toBeGreaterThan(0);
});

test("empty, error, processing, and templated coaching", async ({ page }) => {
  await mockOnlineApi(page, { status: "ready", success: true });
  await fulfillScreens(page, 404, { reason: "not_measured" });
  await page.route(`**/api/stagecoach/sessions/${SESSION_ID}/slides`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ slides: [] }) });
  });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: /screen & flow/i }).click();
  await expect(page.getByTestId("screen-flow-empty")).toBeVisible();
  await shot(page, "screen-flow-empty");

  await fulfillScreens(page, 500, { detail: "nope" });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: /screen & flow/i }).click();
  await expect(page.getByTestId("screen-flow-error")).toBeVisible();
  await expect(page.getByText(/couldn't load the screen list/i)).toBeVisible();
  await expect(page.getByText("Screen & Flow").first()).toBeVisible();

  await mockOnlineApi(page, { status: "partial", screenRunning: true });
  await fulfillScreens(page, 404, { reason: "not_measured" });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: /screen & flow/i }).click();
  await expect(page.getByTestId("screen-flow-processing")).toBeVisible();

  await mockOnlineApi(page, { status: "ready", success: true });
  await fulfillScreens(page, 200, documentFor(4, true));
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: /screen & flow/i }).click();
  await expect(page.getByTestId("flow-coaching-fallback")).toBeVisible();
  await expect(page.getByText(/incorrect/i)).toHaveCount(0);
  await shot(page, "screen-flow-fallback");
});

test("analysis preference saves and reverts", async ({ page }) => {
  await mockOnlineApi(page, { status: "ready", success: true });
  let fail = false;
  await page.route("**/api/stagecoach/me", async (route) => {
    if (route.request().method() === "PATCH") {
      if (fail) return route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
      const body = route.request().postDataJSON() as { review_layout?: string };
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          online_modes_enabled: true,
          review_layout: body.review_layout,
          confirmed_online_layouts: 1,
          retention_policy: "days_30",
        }),
      });
    }
    return route.fallback();
  });
  await page.goto("/settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("review-preference")).toBeVisible();
  await expect(page.getByRole("radio", { name: /when unsure/i })).toBeChecked();
  await shot(page, "analysis-preferences");
  await page.getByText("Never", { exact: true }).click();
  await expect(page.getByText("Saved")).toBeVisible();
  fail = true;
  await page.getByText("Always", { exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("radio", { name: /never/i })).toBeChecked();
});

test("screen and flow has no serious axe violations", async ({ page }) => {
  await mockOnlineApi(page, { status: "ready", success: true });
  await fulfillScreens(page, 200, documentFor(6));
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("tab", { name: /screen & flow/i }).click();
    await expect(page.getByTestId("screen-flow-ready")).toBeVisible();
    const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
    const serious = results.violations.filter((row) => row.impact === "serious" || row.impact === "critical");
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  }
});
