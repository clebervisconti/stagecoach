import type { Page, Route } from "@playwright/test";
import { mockStagecoachApi, SESSION_ID, silentWav } from "./helpers.ts";
import { sampleReport } from "../lib/fixtures/report-sample.ts";
import type { LayoutView } from "../lib/online.ts";

export { SESSION_ID, silentWav };

export function layoutFixture(kind: "high" | "check" | "unsure" | "empty" | "camera" | "screen"): LayoutView {
  const camera = { id: "r0", role: "camera" as const, x: 0.8, y: 0, w: 0.2, h: 0.22, confidence: 0.9 };
  const screen = { id: "r1", role: "screen" as const, x: 0, y: 0, w: 0.8, h: 1, confidence: 0.88 };
  const ignore = { id: "r2", role: "ignore" as const, x: 0.8, y: 0.22, w: 0.2, h: 0.2, confidence: 0.7 };
  const regions =
    kind === "empty" ? [] : kind === "camera" ? [camera] : kind === "screen" ? [screen] : [screen, camera, ignore];
  const confidence = kind === "high" || kind === "camera" || kind === "screen" ? 0.86 : kind === "check" ? 0.68 : kind === "unsure" ? 0.4 : 0.2;
  return {
    session_id: SESSION_ID,
    job_id: "job-1",
    version: 1,
    status: "detected",
    confidence,
    detector_version: "1.0.0",
    frame: { width: 1920, height: 1080, duration_s: 3492 },
    review_reason: kind === "empty" ? "no_regions_found" : kind === "check" ? "camera_tile_low_confidence" : kind === "unsure" ? "screen_region_unclear" : null,
    preview_t: 760,
    auto_confirmed: false,
    segments: [
      {
        index: 0,
        t_start: 0,
        t_end: 3492,
        kind: kind === "camera" ? "camera_full" : kind === "screen" ? "screen_full" : kind === "empty" ? "no_video" : "composite",
        confidence,
        regions,
        preview_url: `/api/v1/sessions/${SESSION_ID}/layout/preview/0?exp=1&sig=x`,
      },
    ],
  };
}

export function onlineReport() {
  return {
    ...sampleReport,
    schema_version: "1.1.0",
    session: { ...sampleReport.session, delivery_mode: "webinar", source_kind: "upload" },
    core_delivery: { score: 74, confidence: 0.81, categories: ["pace_pausing", "vocal_variety", "fluency", "energy_presence"] },
    layout_summary: { kinds: ["composite"], camera_visible_ratio: 1, screen_visible_ratio: 1, version: 1, status: "confirmed" },
    categories: [
      ...sampleReport.categories,
      {
        id: "screen_flow",
        pillar: "visuals",
        applicable: false,
        na_reason: "Coming soon.",
        na_code: "not_in_phase",
        score: null,
        level: null,
        confidence: null,
        confidence_label: null,
        weight_used: 0,
        top_contributors: [],
        evidence_ids: [],
        sources: [],
        counterfactual: null,
      },
      {
        id: "on_camera_presence",
        pillar: "body",
        applicable: false,
        na_reason: "Video analysis is off.",
        na_code: "consent_video_off",
        score: null,
        level: null,
        confidence: null,
        confidence_label: null,
        weight_used: 0,
        top_contributors: [],
        evidence_ids: [],
        sources: [],
        counterfactual: null,
      },
    ],
  };
}

export async function mockOnlineApi(
  page: Page,
  options: {
    title?: string;
    status?: string;
    layout?: LayoutView | null;
    hangUpload?: boolean;
    uploadStatus?: number;
    uploadDetail?: string;
    coreNa?: boolean;
  } = {},
) {
  await mockStagecoachApi(page, { language: "en", title: options.title ?? "Q3 security webinar" });
  const layout = options.layout === undefined ? layoutFixture("high") : options.layout;
  await page.route("**/api/stagecoach/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/stagecoach/, "");
    const method = request.method();
    if (method === "GET" && path === "/me") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-1",
          email: "cleber@example.invalid",
          locale: "en",
          timezone: "UTC",
          accessibility_profile: {},
          retention_policy: "days_30",
          llm_settings: {},
          online_modes_enabled: true,
        }),
      });
    }
    if (method === "POST" && path === "/sessions") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: SESSION_ID,
          title: options.title ?? "Q3 security webinar",
          status: "created",
          delivery_mode: "webinar",
        }),
      });
    }
    if (method === "POST" && path === `/sessions/${SESSION_ID}/upload`) {
      if (options.hangUpload) {
        await new Promise(() => undefined);
        return;
      }
      return route.fulfill({
        status: options.uploadStatus ?? 200,
        contentType: "application/json",
        body: JSON.stringify(
          options.uploadStatus && options.uploadStatus >= 400
            ? { detail: options.uploadDetail ?? "This file is larger than 2 GB. Trim it or export at 720p." }
            : { id: SESSION_ID, status: "preparing" },
        ),
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: SESSION_ID,
          title: options.title ?? "Q3 security webinar",
          status: options.status ?? "preparing",
          context_type: "keynote",
          delivery_mode: "webinar",
          source_kind: "upload",
          language: "en",
          slot_min: 60,
          created_at: "2026-10-22T12:00:00Z",
          job: {
            status: options.status === "failed" ? "failed" : "running",
            error: options.status === "failed" ? { message: "unreadable" } : null,
            created_at: "2026-10-22T12:00:00Z",
            steps: [
              { stage: "ingest", status: "succeeded", message: "Media ready" },
              { stage: "layout", status: options.status === "preparing" ? "running" : "succeeded" },
            ],
          },
        }),
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/layout`) {
      if (!layout) return route.fulfill({ status: 404, body: "" });
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(layout) });
    }
    if (method === "POST" && path === `/sessions/${SESSION_ID}/layout/accept`) {
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "processing", audio_only: false }),
      });
    }
    if (path.includes("/layout/preview") || path.endsWith("/poster")) {
      const png = Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64",
      );
      return route.fulfill({ status: 200, contentType: "image/png", body: png });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/report`) {
      const report = onlineReport();
      if (options.coreNa) report.core_delivery = { score: null, confidence: null, categories: [] };
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(report) });
    }
    return route.fallback();
  });
}
