import { mkdirSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { mockStagecoachApi, SESSION_ID } from "./helpers.ts";

const OUT = "/opt/cursor/artifacts/v3";

test.describe("v3 signal screenshots", () => {
  test.skip(process.env.V3_SHOTS !== "1", "Set V3_SHOTS=1 to capture review screenshots");

  test("capture every mocked screen in both themes", async ({ page }) => {
    test.setTimeout(240_000);
    mkdirSync(OUT, { recursive: true });
    page.on("pageerror", (error) => console.log("PAGEERROR", error.message));
    let list: "empty" | "filled" = "empty";
    let sessionMode: "mock" | "processing" = "mock";

    await mockStagecoachApi(page, { language: "en", title: "Quarterly product update (example)" });
    await page.route("**/api/stagecoach/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace(/^\/api\/stagecoach/, "");
      const method = route.request().method();
      if (method === "GET" && path === "/auth/apple/config") {
        return json(route, { enabled: true });
      }
      if (method === "GET" && path === "/sessions") {
        const sessions = list === "filled"
          ? [
              row(SESSION_ID, "Quarterly product update (example)", "ready", "webinar", "2026-11-12T15:00:00Z", 74),
              row("22222222-2222-4222-8222-222222222222", "Team all-hands (example)", "partial", "online_talk", "2026-11-08T15:00:00Z", 61),
            ]
          : [];
        return json(route, { sessions });
      }
      if (method === "GET" && path === "/me") {
        return json(route, { id: "user-1", email: "ci@example.invalid", locale: "en", online_modes_enabled: true, retention_policy: "days_30" });
      }
      if (method === "GET" && path === `/sessions/${SESSION_ID}`) {
        const processing = sessionMode === "processing";
        return json(route, {
          id: SESSION_ID,
          title: "Quarterly product update (example)",
          status: processing ? "processing" : "ready",
          context_type: "webinar",
          delivery_mode: "webinar",
          language: "en",
          created_at: "2026-11-12T15:00:00Z",
          job: {
            status: processing ? "running" : "succeeded",
            error: null,
            created_at: "2026-11-12T15:00:00Z",
            steps: [
              { stage: "ingest", status: "succeeded" },
              { stage: "asr", status: "succeeded" },
              { stage: "audio_features", status: processing ? "running" : "succeeded" },
              { stage: "fusion_scoring", status: processing ? "pending" : "succeeded" },
              { stage: "report", status: processing ? "pending" : "succeeded" },
            ],
          },
        });
      }
      if (method === "GET" && path === `/sessions/${SESSION_ID}/layout`) {
        return json(route, {
          session_id: SESSION_ID,
          job_id: "job-example",
          version: 1,
          status: "needs_review",
          confidence: 0.8,
          detector_version: "example",
          frame: { width: 1920, height: 1080, duration_s: 120 },
          preview_t: 12,
          segments: [
            {
              index: 0,
              t_start: 0,
              t_end: 120,
              kind: "composite",
              confidence: 0.8,
              regions: [
                { id: "cam", role: "camera", x: 0.7, y: 0.05, w: 0.25, h: 0.3 },
                { id: "scr", role: "screen", x: 0.05, y: 0.08, w: 0.6, h: 0.7 },
              ],
            },
          ],
        });
      }
      return route.fallback();
    });

    for (const theme of ["dark", "light"] as const) {
      for (const width of [1440, 390] as const) {
        await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
        await page.emulateMedia({ reducedMotion: "reduce", colorScheme: theme });
        await applyTheme(page, theme);

        list = "empty";
        sessionMode = "mock";
        await shot(page, "01-sign-in", theme, width, "/sign-in", () => page.getByTestId("apple-signin"));
        await shot(page, "03-sessions-empty", theme, width, "/sessions", () => page.getByTestId("empty-sessions"));

        list = "filled";
        await shot(page, "02-sessions-overview", theme, width, "/sessions", () => page.getByRole("heading", { name: /recent sessions/i }));
        await shot(page, "04-new-session", theme, width, "/sessions/new", () => page.getByTestId("mode-group"));
        await shot(page, "05-session-review", theme, width, `/sessions/${SESSION_ID}`, () => page.getByTestId("report"));
        await page.getByRole("tab", { name: /screen/i }).click();
        await page.waitForTimeout(300);
        await save(page, "08-screen-flow", theme, width);

        sessionMode = "processing";
        await shot(page, "06-report-processing", theme, width, `/sessions/${SESSION_ID}`, () => page.getByTestId("processing"));
        sessionMode = "mock";
        await shot(page, "07-layout-editor", theme, width, `/sessions/${SESSION_ID}/layout`, () => page.locator("#layout-title"));
        await shot(page, "09-settings", theme, width, "/settings", () => page.getByRole("heading", { name: /settings|ajustes/i }));
        await shot(page, "10-error-states", theme, width, "/sessions/33333333-3333-4333-8333-333333333333", () => page.getByTestId("report-load-error"));

        list = "filled";
        await page.goto("/sessions", { waitUntil: "domcontentloaded" });
        await expect(page.getByRole("heading", { name: /recent sessions/i })).toBeVisible();
        await page.getByTestId("command-button").dispatchEvent("click");
        await expect(page.getByTestId("command-palette")).toBeVisible();
        await save(page, "11-command-palette", theme, width);
        await page.keyboard.press("Escape");
      }
    }
  });
});

function row(id: string, title: string, status: string, context: string, created: string, overall: number) {
  return { id, title, status, context_type: context, language: "en", created_at: created, overall };
}

function json(route: import("@playwright/test").Route, body: unknown) {
  return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
}

async function applyTheme(page: Page, theme: "dark" | "light") {
  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
  await page.evaluate((next) => {
    localStorage.setItem("cs-theme", next);
    document.documentElement.dataset.theme = next;
  }, theme);
}

async function shot(page: Page, name: string, theme: string, width: number, path: string, ready?: () => ReturnType<Page["locator"]>) {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  if (ready) await expect(ready()).toBeVisible({ timeout: 15_000 });
  await save(page, name, theme, width);
}

async function save(page: Page, name: string, theme: string, width: number) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 1) {
    const offender = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const hits: string[] = [];
      for (const el of document.querySelectorAll("body *")) {
        const box = el.getBoundingClientRect();
        if (box.right > vw + 1 || box.left < -1) {
          hits.push(`${el.tagName}.${String(el.className).slice(0, 80)} ${Math.round(box.left)}..${Math.round(box.right)}`);
        }
      }
      return hits.slice(0, 6).join(" | ");
    });
    console.log("OVERFLOW", name, width, theme, overflow, offender);
  }
  await page.screenshot({ path: `${OUT}/${name}-${width}-${theme}.png`, fullPage: width >= 1000 });
}
