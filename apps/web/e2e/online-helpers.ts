import type { Page } from "@playwright/test";
import { mockStagecoachApi, SESSION_ID, silentWav } from "./helpers.ts";
import { sampleReport } from "../lib/fixtures/report-sample.ts";
import type { AnalysisReport } from "../lib/report-types.ts";
import type { LayoutView } from "../lib/online.ts";

export { SESSION_ID, silentWav };

export function pastIso(secondsAgo: number): string {
  return new Date(Date.now() - secondsAgo * 1000).toISOString();
}

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
    frame: { width: 1920, height: 1080, duration_s: 540 },
    review_reason: kind === "empty" ? "no_regions_found" : kind === "check" ? "camera_tile_low_confidence" : kind === "unsure" ? "screen_region_unclear" : null,
    preview_t: 120,
    auto_confirmed: false,
    segments: [
      {
        index: 0,
        t_start: 0,
        t_end: 540,
        kind: kind === "camera" ? "camera_full" : kind === "screen" ? "screen_full" : kind === "empty" ? "no_video" : "composite",
        confidence,
        regions,
        preview_url: `/api/v1/sessions/${SESSION_ID}/layout/preview/0?exp=1&sig=x`,
      },
    ],
  };
}

function scoredCategory(id: string, pillar: string, score: number, level: number): AnalysisReport["categories"][number] {
  return {
    id,
    pillar,
    applicable: true,
    na_reason: null,
    na_code: null,
    score,
    level,
    confidence: 0.84,
    confidence_label: "high",
    weight_used: 4,
    top_contributors: [],
    evidence_ids: [],
    sources: [],
    counterfactual: null,
  };
}

export function onlinePartialReport(): AnalysisReport {
  const report = structuredClone(sampleReport) as AnalysisReport;
  report.schema_version = "1.1.0";
  report.session = { ...sampleReport.session!, delivery_mode: "webinar", source_kind: "upload" };
  report.core_delivery = { score: null, confidence: null, categories: [] };
  report.layout_summary = { kinds: ["composite"], camera_visible_ratio: 1, screen_visible_ratio: 1, version: 1, status: "confirmed" };
  report.quality = { warnings: ["Transcription confidence is low; check the transcript."] };
  report.insights = {
    ...report.insights,
    summary: "Measured score 71 ± 4 from 4 of 21 categories. 17 of 21 categories are unavailable.",
    strengths: [
      {
        category_id: "pace_pausing",
        title: "Pace and pausing is a measured strength",
        body: "Pace and pausing scored 80 at level 4.",
        fix: null,
        drill_ids: [],
        evidence_ids: ["ev-2"],
      },
    ],
    weaknesses: [
      {
        category_id: "fluency",
        title: "Fluency needs practice",
        body: "Fluency scored 48 at level 3.",
        fix: "Rehearse the drill once, then re-record the same section.",
        drill_ids: ["pause-instead-of-um"],
        evidence_ids: ["ev-1"],
      },
    ],
    opportunities: [
      {
        category_id: "fluency",
        title: "Practice fluency",
        body: "Fluency is at 48. A target near 73 is the next practice band.",
        fix: "Use the attached drill, then analyse the same talk again.",
        drill_ids: ["pause-instead-of-um"],
        evidence_ids: ["ev-1"],
        impact_estimate: 12,
      },
    ],
  };
  report.categories = [
    ...report.categories.map((category) =>
      category.id === "visual_aids"
        ? { ...category, na_code: "not_in_phase", na_reason: "Coming soon." }
        : category.id === "gestures_body"
          ? { ...category, na_code: "consent_video_off", na_reason: "Video analysis is off." }
          : category,
    ),
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
  ];
  return report;
}

export function onlineSuccessReport(): AnalysisReport {
  const report = structuredClone(sampleReport) as AnalysisReport;
  report.schema_version = "1.1.0";
  report.session = { ...sampleReport.session!, delivery_mode: "webinar", source_kind: "upload" };
  report.provenance = { scoring_config_version: "1.1.0", generated_at: "2026-10-22T12:00:00Z" };
  report.media = { duration_s: 540, has_video: true, has_audio: true };
  report.quality = { warnings: [] };
  report.overall = {
    score: 82,
    level: 4,
    coverage: 0.95,
    confidence: 0.86,
    display_band: 3,
    partial: false,
  };
  report.core_delivery = {
    score: 78,
    confidence: 0.88,
    categories: ["pace_pausing", "vocal_variety", "fluency", "energy_presence", "clarity", "structure", "opening_close"],
  };
  report.layout_summary = { kinds: ["composite"], camera_visible_ratio: 1, screen_visible_ratio: 1, version: 1, status: "confirmed" };
  report.pillars = [
    { id: "message", score: 80, confidence: 0.86, categories: ["core_message", "structure", "opening_close", "clarity"] },
    { id: "story_impact", score: 76, confidence: 0.8, categories: ["storytelling", "audience_adaptation", "impact"] },
    { id: "visuals", score: 74, confidence: 0.78, categories: ["visual_aids"] },
    { id: "voice", score: 81, confidence: 0.88, categories: ["pace_pausing", "vocal_variety", "fluency"] },
    { id: "body", score: 72, confidence: 0.74, categories: ["gestures_body", "eye_contact", "facial_affect"] },
    { id: "presence_time", score: 79, confidence: 0.84, categories: ["energy_presence", "time_management", "qa"] },
  ];
  report.categories = [
    scoredCategory("core_message", "message", 82, 4),
    scoredCategory("structure", "message", 80, 4),
    scoredCategory("opening_close", "message", 78, 4),
    scoredCategory("clarity", "message", 81, 4),
    scoredCategory("storytelling", "story_impact", 75, 4),
    scoredCategory("audience_adaptation", "story_impact", 77, 4),
    scoredCategory("impact", "story_impact", 76, 4),
    scoredCategory("visual_aids", "visuals", 74, 4),
    { ...scoredCategory("pace_pausing", "voice", 80, 4), top_contributors: ["pp_wpm"], evidence_ids: ["ev-2"] },
    scoredCategory("vocal_variety", "voice", 84, 4),
    { ...scoredCategory("fluency", "voice", 72, 4), top_contributors: ["fl_filler_sounds_per_min"], evidence_ids: ["ev-1"] },
    scoredCategory("gestures_body", "body", 70, 4),
    scoredCategory("eye_contact", "body", 73, 4),
    scoredCategory("facial_affect", "body", 71, 4),
    scoredCategory("energy_presence", "presence_time", 79, 4),
    scoredCategory("time_management", "presence_time", 90, 5),
    scoredCategory("qa", "presence_time", 76, 4),
    scoredCategory("on_camera_presence", "body", 74, 4),
    scoredCategory("production_quality", "presence_time", 80, 4),
    scoredCategory("online_engagement", "presence_time", 73, 4),
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
  ];
  report.insights = {
    summary: "Measured score 82 ± 3 from 20 of 21 categories. 1 of 21 categories is unavailable.",
    strengths: [
      {
        category_id: "time_management",
        title: "Time management is a measured strength",
        body: "You used 90% of the slot.",
        fix: null,
        drill_ids: [],
        evidence_ids: [],
      },
    ],
    weaknesses: [],
    opportunities: [
      {
        category_id: "fluency",
        title: "Practice fluency",
        body: "Filler sounds are a little high. Pause instead of filling the gap.",
        fix: "Use the attached drill, then analyse the same talk again.",
        drill_ids: ["pause-instead-of-um"],
        evidence_ids: ["ev-1"],
        impact_estimate: 8,
      },
    ],
  };
  return report;
}

export function onlineReport(): AnalysisReport {
  return onlinePartialReport();
}

function stepsFor(status: string | undefined, autoConfirmed: boolean) {
  if (status === "processing") {
    return [
      { stage: "ingest", status: "succeeded", message: "Media ready" },
      { stage: "layout", status: "succeeded" },
      { stage: "layout_review", status: "succeeded", message: autoConfirmed ? "Confirmed automatically" : "By you" },
      { stage: "asr", status: "succeeded", message: "Transcript ready" },
      { stage: "audio_features", status: "running", message: "Measuring pace and pauses" },
    ];
  }
  if (status === "ready" || status === "partial") {
    return [
      { stage: "ingest", status: "succeeded", message: "Media ready" },
      { stage: "layout", status: "succeeded" },
      { stage: "layout_review", status: "succeeded", message: "By you" },
      { stage: "asr", status: "succeeded" },
      { stage: "audio_features", status: "succeeded" },
      { stage: "fusion_scoring", status: "succeeded" },
      { stage: "report", status: "succeeded" },
    ];
  }
  return [
    { stage: "ingest", status: "succeeded", message: "Media ready" },
    { stage: "layout", status: status === "failed" ? "failed" : "running" },
  ];
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
    startedAgo?: number;
    autoConfirmed?: boolean;
    consentOff?: boolean;
    locale?: "en" | "pt-BR";
    success?: boolean;
  } = {},
) {
  const locale = options.locale ?? "en";
  await mockStagecoachApi(page, { language: locale, title: options.title ?? "Q3 security webinar" });
  const layout = options.layout === undefined ? layoutFixture("high") : options.layout;
  if (options.autoConfirmed && layout) layout.auto_confirmed = true;
  const startedAgo = options.startedAgo ?? (options.status === "processing" ? 45 : 15);
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
          locale,
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
            ? { detail: options.uploadDetail ?? "This file is 2.4 GB. The limit is 2 GB. Trim it or export at 720p." }
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
          language: locale === "pt-BR" ? "pt-BR" : "en",
          slot_min: 60,
          created_at: pastIso(startedAgo + 20),
          job: {
            status: options.status === "failed" ? "failed" : "running",
            error: options.status === "failed" ? { message: "unreadable" } : null,
            created_at: pastIso(startedAgo),
            steps: stepsFor(options.status, Boolean(options.autoConfirmed || options.consentOff)),
          },
        }),
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/events`) {
      const body =
        options.status === "processing"
          ? [
              `data: ${JSON.stringify({ type: "connected", job_id: "job-1" })}`,
              `data: ${JSON.stringify({ type: "stage", stage: "audio_features", status: "running" })}`,
            ].join("\n\n")
          : `data: ${JSON.stringify({ type: "connected", job_id: "job-1" })}`;
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: { "cache-control": "no-cache", connection: "keep-alive" },
        body: `${body}\n\n`,
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
      const report = options.success ? onlineSuccessReport() : onlinePartialReport();
      if (options.coreNa) report.core_delivery = { score: null, confidence: null, categories: [] };
      if (options.consentOff) {
        const camera = report.categories.find((category) => category.id === "on_camera_presence");
        if (camera) {
          camera.applicable = false;
          camera.score = null;
          camera.na_code = "consent_video_off";
          camera.na_reason = "Video analysis is off.";
        }
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(report) });
    }
    return route.fallback();
  });
}
