import { expect, test } from "@playwright/test";
import { mockStagecoachApi, SESSION_ID } from "./helpers.ts";

test("trends goals panel creates and lists progress", async ({ page }) => {
  const goals: Array<Record<string, unknown>> = [];
  await page.route("**/api/stagecoach/trends**", async (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        filters: { context: "exec_briefing" },
        series: [],
        sparkline: [],
        most_improved: null,
        needs_attention: null,
        comparable_count: 0,
      }),
    });
  });
  await page.route("**/api/stagecoach/goals**", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const created = {
        id: "goal-1",
        ...body,
        latest_value: 2.8,
        achieved_at: "2026-10-16T00:00:00",
        label: `${body.metric_id || body.category_id} ${body.comparator} ${body.target}: 2.8 ✓`,
      };
      goals.push(created);
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(created),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ goals }),
    });
  });

  await page.goto("/trends", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("goals-panel")).toBeVisible();
  await page.getByTestId("goal-key").fill("fl_filler_sounds_per_min");
  await page.getByTestId("goal-submit").click();
  await expect(page.getByTestId("goal-row")).toContainText("fl_filler_sounds_per_min");
  await expect(page.getByTestId("goal-row")).toContainText("✓");
});

test("session radar draws a dashed goal polygon", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "Goals radar talk" });
  await page.route("**/api/stagecoach/goals**", async (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        goals: [{ category_id: "fluency", target: 80, comparator: ">=" }],
      }),
    });
  });
  await page.goto(`/sessions/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("report")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("goal-polygon")).toBeAttached();
  await expect(page.getByTestId("goal-vertex").first()).toBeVisible();
});
