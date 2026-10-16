import { expect, test } from "@playwright/test";

const PLAN_ID = "11111111-1111-4111-8111-111111111161";

test("plan editor edits a section and exports markdown", async ({ page }) => {
  await page.route(`**/api/stagecoach/plans/${PLAN_ID}**`, async (route) => {
    const method = route.request().method();
    const url = route.request().url();
    if (method === "POST" && url.includes("/regenerate")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: PLAN_ID,
          title: "Board update",
          context_type: "exec_briefing",
          slot_min: 20,
          outputs: { core_message: "Approve the pilot this quarter" },
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: PLAN_ID,
        title: "Board update",
        context_type: "exec_briefing",
        slot_min: 20,
        audience: { roles: "executives" },
        outputs: { status: "placeholder" },
      }),
    });
  });

  await page.goto(`/prep/${PLAN_ID}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("plan-editor")).toBeVisible();
  await expect(page.getByTestId("section-core_message")).toBeVisible();
  await expect(page.getByTestId("readiness")).toContainText("N/A until a rehearsal");
  await expect(page.getByTestId("top-changes")).toBeVisible();
  await page.getByTestId("regen-core_message").click();
  await expect(page.getByTestId("section-core_message").locator("textarea")).toHaveValue(
    /Approve the pilot/,
  );
  const download = page.waitForEvent("download");
  await page.getByTestId("export-markdown").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.md$/);
});
