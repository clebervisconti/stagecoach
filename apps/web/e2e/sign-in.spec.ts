import { expect, test } from "@playwright/test";

test("sign-in hides Apple and public registration until an invite exists", async ({ page }) => {
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
      const body = route.request().postDataJSON() as { invite?: string };
      expect(body.invite).toBe("example-invite");
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
  await expect(page.getByTestId("brand-lockup")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByTestId("apple-signin")).toHaveCount(0);
  await expect(page.getByText(/secrets|stand-in|D10/i)).toHaveCount(0);
  await expect(page.getByTestId("auth-register")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /verification token/i })).toHaveAttribute("href", "/verify-request");

  await page.goto("/sign-in?mode=register&invite=example-invite", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  await expect(page.getByText(/at least 10 characters/i)).toBeVisible();
  await page.getByTestId("auth-email").fill("speaker@example.invalid");
  await page.getByTestId("auth-password").fill("correct-horse-battery");
  await page.getByTestId("auth-submit").click();
  await expect(page.getByText(/inbox/i)).toBeVisible();
  await expect(page.getByText(/console|stand-in|token de verificação/i)).toHaveCount(0);
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

  await page.goto("/sign-in?mode=register", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("apple-signin")).toHaveCount(0);

  await page.goto("/sign-in?mode=register&invite=example-invite", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("apple-signin")).toBeVisible();
});

test("Apple callback explains a cancellation without internal detail", async ({ page }) => {
  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    sessionStorage.setItem(
      "apple-oidc",
      JSON.stringify({ verifier: "v", nonce: "n", state: "s", redirect: "http://localhost/auth/apple/callback" }),
    );
  });
  await page.goto("/auth/apple/callback?error=user_cancelled_authorize&state=s", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("apple-callback")).toHaveAttribute("data-state", "cancelled");
  await expect(page.getByText(/PKCE|secret|id_token/i)).toHaveCount(0);
});
