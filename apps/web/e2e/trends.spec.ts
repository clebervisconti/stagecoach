import { expect, test } from "@playwright/test";

test("trends dashboard marks incompatible sessions", async ({ page }) => {
  await page.route("**/api/stagecoach/trends**", async (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        filters: { context: "exec_briefing" },
        series: [
          {
            session_id: "s1",
            title: "Briefing A",
            comparable: true,
            overall: 72,
            value: 72,
          },
          {
            session_id: "s2",
            title: "Keynote",
            comparable: false,
            reason: "different context",
            overall: 80,
            value: 80,
          },
        ],
        sparkline: [60, 72],
        most_improved: { session_id: "s1", delta: 12, from: 60, to: 72 },
        needs_attention: null,
        comparable_count: 1,
      }),
    });
  });

  await page.goto("/trends", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("trends-page")).toBeVisible();
  await expect(page.getByTestId("nav-trends")).toBeVisible();
  await expect(page.getByTestId("trends-table")).toContainText("Not comparable");
  await expect(page.getByTestId("trends-table")).toContainText("different context");
  await expect(page.getByTestId("trends-sparkline")).toBeVisible();
});
