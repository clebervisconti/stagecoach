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
  const ready = () => firstSessionGet > 0 && Date.now() - firstSessionGet > 1200;
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
    if (method === "GET" && path === `/sessions/${SESSION_ID}`) {
      if (!firstSessionGet) firstSessionGet = Date.now();
      return json(route, session());
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
    if (method === "DELETE" && path === `/sessions/${SESSION_ID}`) {
      deleted = true;
      return route.fulfill({ status: 204, body: "" });
    }
    return json(route, { detail: `unmocked ${method} ${path}` }, 501);
  });

  return { deleted: () => deleted };
}
