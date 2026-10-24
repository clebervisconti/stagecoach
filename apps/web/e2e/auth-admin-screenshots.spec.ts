import { expect, test, type Page, type Route } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { sessionCookie } from "./session-cookie.ts";

const OUT = process.env.AUTH_SCREEN_DIR || "/opt/cursor/artifacts/screenshots";
const WIDTHS = [390, 1440] as const;
const THEMES = ["light", "dark"] as const;
const STATES = ["empty", "loading", "error", "success"] as const;

const USERS = {
  users: [
    {
      id: "11111111-1111-4111-8111-111111111102",
      email: "admin@example.com",
      name: "Admin Example",
      role: "admin",
      disabled: false,
      must_change_password: false,
      online_modes: false,
      email_verified: true,
      apple_linked: false,
    },
    {
      id: "11111111-1111-4111-8111-111111111103",
      email: "member@example.com",
      name: "Member Example",
      role: "member",
      disabled: false,
      must_change_password: true,
      online_modes: true,
      email_verified: true,
      apple_linked: true,
    },
  ],
  total: 2,
};

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function themeAndWidth(page: Page, width: number, theme: string) {
  await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  await page.addInitScript((next) => {
    localStorage.setItem("cs-theme", next);
    document.documentElement.dataset.theme = next;
  }, theme);
}

async function snap(page: Page, screen: string, state: string, width: number, theme: string) {
  mkdirSync(OUT, { recursive: true });
  if (width === 390) {
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(390);
  }
  await page.screenshot({
    path: `${OUT}/${screen}_${state}_${width}_${theme}.png`,
    fullPage: true,
  });
}

async function memberCookie(page: Page, mustChangePassword: boolean, role = "member") {
  await page.context().clearCookies();
  await page.context().addCookies([
    await sessionCookie({
      email: role === "admin" ? "admin@example.com" : "member@example.com",
      role,
      mustChangePassword,
      id: role === "admin" ? "11111111-1111-4111-8111-111111111102" : "11111111-1111-4111-8111-111111111103",
    }),
  ]);
}

test.describe("auth screenshots", () => {
  test.describe.configure({ timeout: 60_000 });

  for (const width of WIDTHS) {
    for (const theme of THEMES) {
      for (const state of STATES) {
        test(`login ${state} ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await page.context().clearCookies();
          if (state === "loading") {
            await page.route("**/api/stagecoach/auth/login", async (route) => {
              await new Promise((resolve) => setTimeout(resolve, 4000));
              await json(route, 200, { session_ticket: "ticket", must_change_password: false });
            });
          }
          if (state === "error") {
            await page.route("**/api/stagecoach/auth/login", async (route) => {
              await json(route, 401, { detail: "Invalid email or password" });
            });
          }
          if (state === "success") {
            await page.route("**/api/stagecoach/auth/login", async (route) => {
              await json(route, 200, {
                session_ticket: "ticket",
                must_change_password: false,
                id: "11111111-1111-4111-8111-111111111103",
                email: "member@example.com",
                role: "member",
                session_version: 1,
              });
            });
          }
          await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
          await expect(page.getByTestId("sign-in-form")).toBeVisible();
          if (state !== "empty") {
            if (state === "success") {
              await page.route("**/api/auth/**", async (route) => {
                await new Promise((resolve) => setTimeout(resolve, 20000));
                await json(route, 200, {});
              });
            }
            await page.getByTestId("auth-email").fill("member@example.com");
            await page.getByTestId("auth-password").fill("temp-pass");
            await page.getByTestId("auth-submit").click();
            await expect(page.getByTestId("sign-in-form")).toHaveAttribute("data-state", state);
          } else {
            await expect(page.getByTestId("sign-in-form")).toHaveAttribute("data-state", "empty");
          }
          await snap(page, "login", state, width, theme);
        });

        test(`forced-change ${state} ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await memberCookie(page, true);
          if (state === "loading") {
            await page.route("**/api/stagecoach/auth/password", async (route) => {
              await new Promise((resolve) => setTimeout(resolve, 4000));
              await json(route, 200, { session_ticket: "ticket", must_change_password: false });
            });
          }
          if (state === "error") {
            await page.route("**/api/stagecoach/auth/password", async (route) => {
              await json(route, 401, { detail: "Current password is incorrect" });
            });
          }
          if (state === "success") {
            await page.route("**/api/stagecoach/auth/password", async (route) => {
              await json(route, 200, { session_ticket: "ticket", must_change_password: false });
            });
          }
          await page.goto("/account/password", { waitUntil: "domcontentloaded" });
          await expect(page.getByTestId("password-change")).toBeVisible();
          if (state !== "empty") {
            if (state === "success") {
              await page.route("**/api/auth/**", async (route) => {
                await new Promise((resolve) => setTimeout(resolve, 20000));
                await json(route, 200, {});
              });
            }
            await page.getByTestId("password-current").fill("temp-pass");
            await page.getByTestId("password-new").fill("correct-horse-battery");
            await page.getByTestId("password-confirm").fill("correct-horse-battery");
            await page.getByTestId("password-submit").click();
            await expect(page.getByTestId("password-change")).toHaveAttribute("data-state", state);
          }
          await snap(page, "forced-change", state, width, theme);
        });

        test(`admin-users ${state} ${width} ${theme}`, async ({ page }) => {
          await themeAndWidth(page, width, theme);
          await memberCookie(page, false, "admin");
          await page.route("**/api/stagecoach/me", async (route) => {
            await json(route, 200, {
              email: "admin@example.com",
              role: "admin",
              must_change_password: false,
              online_modes_enabled: false,
            });
          });
          await page.route("**/api/stagecoach/admin/users**", async (route) => {
            if (route.request().method() !== "GET") return route.fallback();
            if (state === "loading") {
              await new Promise((resolve) => setTimeout(resolve, 4000));
              return json(route, 200, USERS);
            }
            if (state === "error") return json(route, 500, { detail: "Could not load users." });
            if (state === "empty") return json(route, 200, { users: [], total: 0 });
            return json(route, 200, USERS);
          });
          await page.goto("/admin/users", { waitUntil: "domcontentloaded" });
          await expect(page.getByTestId("admin-users")).toHaveAttribute("data-state", state, { timeout: 15_000 });
          await snap(page, "admin-users", state, width, theme);
        });
      }
    }
  }
});
