import { expect, test } from "@playwright/test";

test("sign-in form registers and hides Apple until secrets exist", async ({ page }) => {
  await page.route("**/api/stagecoach/auth/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname.replace(/^\/api\/stagecoach/, "");
    if (method === "GET" && path === "/auth/apple/config") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: false }),
      });
    }
    if (method === "POST" && path === "/auth/register") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ status: "accepted", email: "speaker@example.invalid" }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("sign-in-form")).toBeVisible();
  await expect(page.getByTestId("apple-disabled")).toBeVisible();
  await page.getByTestId("auth-register").click();
  await page.getByTestId("auth-email").fill("speaker@example.invalid");
  await page.getByTestId("auth-password").fill("correct-horse-battery");
  await page.getByTestId("auth-submit").click();
  await expect(page.getByText(/verification token/i)).toBeVisible();
});

test("Sign in with Apple button appears when the API says enabled", async ({ page }) => {
  await page.route("**/api/stagecoach/auth/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/stagecoach/, "");
    if (path === "/auth/apple/config") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: true }),
      });
    }
    if (path === "/auth/apple/start") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authorize_url: "https://appleid.apple.com/auth/authorize?nonce=n&code_challenge=c",
          verifier: "v",
          nonce: "n",
          state: "s",
        }),
      });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });

  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("apple-signin")).toBeVisible();
});
