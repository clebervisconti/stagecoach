import type { Page, Route } from "@playwright/test";
import { sampleReport } from "../lib/fixtures/report-sample.ts";
import type { AnalysisReport } from "../lib/report-types.ts";

export const SESSION_ID = "11111111-1111-4111-8111-111111111136";

export function silentWav(seconds = 0.25, sampleRate = 16000): Buffer {
  const samples = Math.max(1, Math.floor(sampleRate * seconds));
  const dataSize = samples * 2;
  const buf = Buffer.alloc(44 + dataSize);
  buf.write("RIFF", 0);
  buf.writeUInt32LE(36 + dataSize, 4);
  buf.write("WAVE", 8);
  buf.write("fmt ", 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * 2, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write("data", 36);
  buf.writeUInt32LE(dataSize, 40);
  return buf;
}

type MockOptions = {
  language: "en" | "pt-BR";
  title: string;
  stayProcessing?: boolean;
};

function ptTranscript() {
  return {
    language: "pt-BR",
    duration: 12,
    segments: [
      {
        id: "S0001",
        start: 0,
        end: 10,
        speaker: "SPK_0",
        text: "Legal né foi tipo assim estranho então vamos começar",
        words: [
          { word: "Legal", start: 0.0, end: 0.4 },
          { word: "né", start: 0.4, end: 0.7 },
          { word: "foi", start: 1.0, end: 1.3 },
          { word: "tipo", start: 1.3, end: 1.6 },
          { word: "assim", start: 1.6, end: 2.0 },
          { word: "estranho", start: 2.0, end: 2.5 },
          { word: "então", start: 3.0, end: 3.4 },
          { word: "vamos", start: 3.4, end: 3.8 },
          { word: "começar", start: 3.8, end: 4.4 },
        ],
      },
    ],
    disambiguations: [
      {
        hit_id: "hit-0001",
        word: "né",
        token: "né",
        t_start: 0.4,
        t_end: 0.7,
        context_before: "legal",
        context_after: "foi tipo assim",
        is_filler: true,
        confidence: 0.85,
        method: "heuristic_v1",
      },
      {
        hit_id: "hit-0002",
        word: "tipo",
        token: "tipo",
        t_start: 1.3,
        t_end: 1.6,
        context_before: "foi",
        context_after: "assim estranho",
        is_filler: true,
        confidence: 0.9,
        method: "heuristic_v1",
      },
      {
        hit_id: "hit-0003",
        word: "então",
        token: "então",
        t_start: 3.0,
        t_end: 3.4,
        context_before: "estranho",
        context_after: "vamos começar",
        is_filler: false,
        confidence: 0.8,
        method: "heuristic_v1",
      },
    ],
  };
}

function enTranscript() {
  return {
    language: "en",
    duration: 8,
    segments: [
      {
        id: "S0001",
        start: 0,
        end: 6,
        speaker: "SPK_0",
        text: "Um hello everyone",
        words: [
          { word: "Um", start: 0, end: 0.4, tags: ["filler_sound"] },
          { word: "hello", start: 0.5, end: 0.9 },
          { word: "everyone", start: 1.0, end: 1.6 },
        ],
      },
    ],
    disambiguations: [],
  };
}

function reportFor(language: "en" | "pt-BR"): AnalysisReport {
  return {
    ...sampleReport,
    session: { ...sampleReport.session, language },
  };
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export async function mockStagecoachApi(page: Page, options: MockOptions): Promise<{ deleted: () => boolean }> {
  let created = false;
  let deleted = false;
  let firstSessionGet = 0;
  const ready = () =>
    !options.stayProcessing && firstSessionGet > 0 && Date.now() - firstSessionGet > 1200;
  const session = () => ({
    id: SESSION_ID,
    title: options.title,
    status: ready() ? "partial" : "processing",
    context_type: "keynote",
    language: options.language,
    slot_min: 10,
    camera_setup: "audio_only",
    created_at: "2026-10-14T00:00:00Z",
    job: {
      status: ready() ? "succeeded" : "running",
      error: null,
      steps: ["ingest", "asr", "audio_features", "fusion_scoring", "report"].map((stage) => ({
        stage,
        status: ready() ? "succeeded" : "running",
      })),
    },
  });

  const consents = {
    policy_id: "1.0.0",
    policy_version: "0".repeat(64),
    locale: options.language,
    consents: [
      {
        purpose: "video_analysis",
        granted: false,
        granted_at: null,
        revoked_at: null,
        version: null,
        title: "Video analysis",
        what: "Pose and face landmarks as per-second aggregates.",
        why: "Gesture and audience-facing metrics.",
        limits: "Accuracy drops in low light.",
        never: "No emotion inference. No face recognition.",
      },
      {
        purpose: "expression_analysis",
        granted: false,
        granted_at: null,
        revoked_at: null,
        version: null,
        title: "Expression analysis",
        what: "Descriptive facial-movement signals. Off by default.",
        why: "Optional category 14.",
        limits: "Off unless this toggle is on.",
        never: "The app does not infer inner states.",
      },
      {
        purpose: "keep_detailed_tracking",
        granted: false,
        granted_at: null,
        revoked_at: null,
        version: null,
        title: "Keep detailed tracking",
        what: "Optional 30-day raw landmarks.",
        why: "Re-analysis without re-running detection.",
        limits: "Deleted with the session or after 30 days.",
        never: "Not identity templates.",
      },
    ],
  };

  await page.route("**/api/stagecoach/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/stagecoach/, "");
    const method = request.method();

    if (method === "GET" && path === "/goals") {
      return json(route, { goals: [] });
    }
    if (method === "GET" && path === "/me") {
      return json(route, {
        id: "user-1",
        email: "ci@example.invalid",
        locale: "en",
        timezone: "UTC",
        accessibility_profile: {
          seated: false,
          wheelchair: false,
          limited_mobility: false,
          one_handed: false,
          speech_difference: false,
          prefers_no_video_metrics: false,
          low_vision: false,
        },
        retention_policy: "days_30",
        llm_settings: { provider: "xai", base_url: "", model: "", leaves_machine: false },
      });
    }
    if (method === "GET" && path === "/me/ai-providers") {
      return json(route, {
        default_provider: "xai",
        llm_settings: { provider: "xai", base_url: "", model: "", leaves_machine: false },
        providers: [
          { id: "xai", default: true, leaves_machine: false, key_envs: ["XAI_API_KEY"], key_configured: false, needs_base_url: false, default_base_url: "https://api.x.ai/v1" },
        ],
      });
    }
    if (method === "PATCH" && path === "/me") {
      return json(route, {
        id: "user-1",
        email: "ci@example.invalid",
        locale: "en",
        timezone: "UTC",
        accessibility_profile: {
          seated: false,
          wheelchair: false,
          limited_mobility: false,
          one_handed: false,
          speech_difference: false,
          prefers_no_video_metrics: false,
          low_vision: false,
        },
        retention_policy: "days_30",
        llm_settings: { provider: "xai", base_url: "", model: "", leaves_machine: false },
      });
    }
    if (method === "GET" && path === "/me/consents") {
      return json(route, consents);
    }
    if (method === "POST" && path === "/me/consents") {
      const body = request.postDataJSON() as { purpose?: string; granted?: boolean };
      const item = consents.consents.find((row) => row.purpose === body.purpose);
      if (item && typeof body.granted === "boolean") item.granted = body.granted;
      return json(route, consents, 201);
    }
    if (method === "GET" && path === "/sessions") {
      return json(route, { sessions: created && !deleted ? [session()] : [] });
    }
    if (method === "POST" && path === "/sessions") {
      created = true;
      return json(route, session());
    }
    if (method === "POST" && path === `/sessions/${SESSION_ID}/upload`) {
      return json(route, { id: SESSION_ID, status: "processing" });
    }
    if (method === "POST" && path === `/sessions/${SESSION_ID}/deck`) {
      return json(route, { session_id: SESSION_ID, kind: "pptx", bytes: 0 }, 201);
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}`) {
      if (!firstSessionGet) firstSessionGet = Date.now();
      return json(route, session());
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/events`) {
      const body = [
        `data: ${JSON.stringify({ type: "connected", job_id: "job-1" })}`,
        `data: ${JSON.stringify({
          type: "partial_ready",
          categories: ["pace_pausing", "fluency", "vocal_variety"],
        })}`,
        `data: ${JSON.stringify({ type: "stage", stage: "asr", status: "succeeded", pct: 60 })}`,
      ].join("\n\n");
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: { "cache-control": "no-cache", connection: "keep-alive" },
        body: `${body}\n\n`,
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/report`) {
      return json(route, reportFor(options.language));
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/transcript`) {
      return json(route, options.language.startsWith("pt") ? ptTranscript() : enTranscript());
    }
    if (method === "GET" && path.startsWith(`/sessions/${SESSION_ID}/series/`)) {
      return json(route, { name: path.split("/").pop(), resolution_s: 1, points: [], unavailable: true });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/body`) {
      return json(route, {
        available: true,
        duration_s: 12,
        heat: [{ t: 0, value: 0.6 }],
        space: { cols: 8, rows: 6, samples: 2, cells: [0, 2, 0, 1] },
        events: [{ type: "self_adaptor", t_start: 1.2, t_end: 2.0 }],
        sway: { value: 0.11, applicable: true, unit: "shoulder_widths_sd" },
        yaw_histogram: [{ center: -10, count: 4 }],
        audience_facing_ratio: 0.7,
        notes_down: [{ type: "notes_down", t_start: 3, t_end: 5 }],
        expressivity: { available: false, opt_in: true, points: [] },
        quality: {
          person_visible_ratio: 0.9,
          face_visible_ratio: 0.8,
          mean_face_height_px: 90,
          mean_person_height_px: 240,
        },
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/slides`) {
      return json(route, {
        available: true,
        slides: [
          {
            index: 1,
            t_start: 0,
            t_end: 8,
            dwell_s: 8,
            word_count: 12,
            title: "Roadmap",
            title_type: "topic",
            glance_level: null,
            reading_overlap: 0.2,
            facing_screen_s: 1.5,
            has_keyframe: false,
            suggested_title: "We shipped the Q3 roadmap.",
            suggestion_source: "ai",
          },
        ],
        ai_suggestions: true,
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/keyframe`) {
      return route.fulfill({ status: 404, body: "" });
    }
    if (method === "POST" && path === `/sessions/${SESSION_ID}/export/pdf`) {
      return json(route, { id: "export-1", status: "queued" }, 202);
    }
    if (method === "GET" && path === "/exports/export-1") {
      return json(route, {
        id: "export-1",
        status: "ready",
        include_transcript: false,
        download: "/api/v1/exports/export-1/file",
      });
    }
    if (method === "GET" && path === "/exports/export-1/file") {
      return route.fulfill({
        status: 200,
        contentType: "application/pdf",
        body: "%PDF-1.4 mock",
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/timeline`) {
      return json(route, {
        duration_s: 12,
        sprite_interval_s: 5,
        sprite_count: 0,
        lanes: [
          {
            id: "fillers",
            available: true,
            default_on: true,
            items: [{ t_start: 0.4, t_end: 0.7, label: "Um", kind: "filler" }],
          },
          { id: "smiles", available: false, opt_in: true, default_on: false, items: [] },
        ],
      });
    }
    if (method === "GET" && path === `/sessions/${SESSION_ID}/sprite`) {
      return route.fulfill({ status: 404, body: "" });
    }
    if (method === "DELETE" && path === `/sessions/${SESSION_ID}`) {
      deleted = true;
      return route.fulfill({ status: 204, body: "" });
    }
    return json(route, { detail: `unmocked ${method} ${path}` }, 501);
  });

  return { deleted: () => deleted };
}
