import { expect, test } from "@playwright/test";

test("plan form submits and can skip clarifying questions", async ({ page }) => {
  await page.route("**/api/stagecoach/plans**", async (route) => {
    const request = route.request();
    const url = request.url();
    if (request.method() === "POST" && /\/plans\/?$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ id: "11111111-1111-4111-8111-111111111156" }),
      });
    }
    if (url.includes("/clarify")) {
      const body = (request.postDataJSON() as { skip?: boolean } | null) || {};
      if (body.skip) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            questions: [],
            assumptions: ["Assuming a 20-minute slot with no Q&A inside it (not stated)."],
            skipped: true,
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          questions: [{ id: "goal", prompt: "What should the audience believe or do afterwards?" }],
          assumptions: [],
          skipped: false,
        }),
      });
    }
    return route.fulfill({ status: 404, body: "" });
  });

  await page.goto("/prep", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("prep-page")).toBeVisible();
  await expect(page.getByTestId("nav-prep")).toBeVisible();
  await expect(page.getByTestId("plan-form")).toBeVisible();
  await page.locator('input[name="title"]').fill("Board update");
  await page.getByTestId("plan-description").fill("Tell them about the project");
  await page.getByTestId("plan-submit").click();
  await expect(page.getByTestId("clarify-questions")).toBeVisible();
  await page.getByTestId("skip-clarify").click();
  await expect(page.getByTestId("clarify-assumptions")).toBeVisible();
});
