import assert from "node:assert/strict";
import { test } from "node:test";
import { PIPELINE_STAGES, parseProgressData, pipelineStages, pipelineTimeline, sessionConsentOff, shouldReloadReport, stageProblem } from "./progress.ts";

test("partial_ready carries scored category ids", () => {
  const event = parseProgressData(
    JSON.stringify({
      type: "partial_ready",
      categories: ["pace_pausing", "fluency", "vocal_variety"],
    }),
  );
  assert.equal(event?.type, "partial_ready");
  if (event?.type === "partial_ready") {
    assert.deepEqual(event.categories, ["pace_pausing", "fluency", "vocal_variety"]);
  }
  assert.equal(shouldReloadReport(event), true);
});

test("stage events do not force a report reload", () => {
  const event = parseProgressData(
    JSON.stringify({ type: "stage", stage: "vision", status: "running", pct: 42 }),
  );
  assert.equal(event?.type, "stage");
  assert.equal(shouldReloadReport(event), false);
});

test("an ingest stage event keeps the sub-step, the poster, and the duration", () => {
  const event = parseProgressData(
    JSON.stringify({
      type: "stage",
      stage: "ingest",
      status: "running",
      pct: 10,
      message: "ingest_poster",
      eta_s: 240,
      artifact: "poster",
      duration_s: 2149.2,
    }),
  );
  assert.equal(event?.type, "stage");
  if (event?.type === "stage") {
    assert.equal(event.message, "ingest_poster");
    assert.equal(event.eta_s, 240);
    assert.equal(event.artifact, "poster");
    assert.equal(event.duration_s, 2149.2);
  }
});

test("done reloads the final report", () => {
  const event = parseProgressData(JSON.stringify({ type: "done", status: "partial" }));
  assert.equal(event?.type, "done");
  assert.equal(shouldReloadReport(event), true);
});

test("timeline keeps the full pipeline and names the running stage", () => {
  const view = pipelineTimeline(
    [
      { stage: "ingest", status: "succeeded", message: "Media ready" },
      { stage: "asr", status: "running", message: "Transcribing" },
    ],
    null,
  );
  assert.equal(view.find((stage) => stage.stage === "ingest")?.status, "succeeded");
  assert.equal(view.find((stage) => stage.stage === "asr")?.status, "running");
  assert.equal(view.find((stage) => stage.stage === "report")?.status, "pending");
  assert.equal(view.length >= 9, true);
});

test("a live stage event overrides the stored step", () => {
  const view = pipelineTimeline(
    [{ stage: "slides", status: "pending" }],
    { type: "stage", stage: "slides", status: "running", message: "Detecting scenes" },
  );
  const slides = view.find((stage) => stage.stage === "slides");
  assert.equal(slides?.status, "running");
  assert.equal(slides?.detail, "Detecting scenes");
});

test("a missing MediaPipe install becomes a named problem", () => {
  assert.equal(stageProblem("ModuleNotFoundError: No module named 'mediapipe'"), "visionUnavailable");
  const view = pipelineTimeline(
    [
      {
        stage: "vision",
        status: "failed",
        error: "ModuleNotFoundError: No module named 'mediapipe'",
      },
    ],
    null,
  );
  const vision = view.find((stage) => stage.stage === "vision");
  assert.equal(vision?.problem, "visionUnavailable");
  assert.equal(vision?.detail, null);
});

test("an unavailable model is skipped and keeps its reason", () => {
  const view = pipelineTimeline(
    [
      {
        stage: "content_llm",
        status: "unavailable",
        message: "The language model was unavailable.",
      },
    ],
    null,
  );
  const content = view.find((stage) => stage.stage === "content_llm");
  assert.equal(content?.status, "skipped");
  assert.equal(content?.detail, "The language model was unavailable.");
});

test("a skipped vision step names the missing install", () => {
  const view = pipelineTimeline(
    [{ stage: "vision", status: "skipped", message: "mediapipe_unavailable" }],
    null,
  );
  const vision = view.find((stage) => stage.stage === "vision");
  assert.equal(vision?.status, "skipped");
  assert.equal(vision?.problem, "visionUnavailable");
});

test("consent-off comes from the explicit signal, not a skipped vision step", () => {
  assert.equal(stageProblem("consent_denied:video_analysis"), "consent_video_off");
  assert.equal(
    sessionConsentOff({
      consent: { video_analysis: true },
      job: { steps: [{ stage: "vision", status: "skipped", problem: "visionUnavailable", message: "mediapipe_unavailable" }] },
    }),
    false,
  );
  assert.equal(
    sessionConsentOff({
      consent: { video_analysis: false },
      job: { steps: [{ stage: "vision", status: "skipped", problem: "consent_video_off" }] },
    }),
    true,
  );
  assert.equal(
    sessionConsentOff({
      job: { steps: [{ stage: "layout", status: "skipped" }, { stage: "vision", status: "skipped" }] },
    }),
    false,
  );
});

test("online pipeline lists layout and production quality and hides alignment", () => {
  const stages = pipelineStages("webinar", "upload");
  assert.equal(stages.includes("layout"), true);
  assert.equal(stages.includes("production_quality"), true);
  assert.equal(stages.includes("alignment"), false);
  assert.deepEqual(pipelineStages("stage"), [
    "ingest",
    "asr",
    "alignment",
    "audio_features",
    "partial_scoring",
    "vision",
    "slides",
    "content_llm",
    "fusion_scoring",
    "report",
  ]);
});

test("online timeline folds alignment into transcribing and keeps waiting", () => {
  const view = pipelineTimeline(
    [
      { stage: "ingest", status: "succeeded" },
      { stage: "asr", status: "succeeded", message: "Transcript ready" },
      { stage: "alignment", status: "running", message: "Aligning words" },
    ],
    null,
    { deliveryMode: "webinar" },
  );
  assert.equal(view.some((stage) => stage.stage === "alignment"), false);
  assert.equal(view.find((stage) => stage.stage === "asr")?.status, "running");

  const waiting = pipelineTimeline(
    [{ stage: "layout_review", status: "waiting", message: "Check the layout" }],
    null,
    { deliveryMode: "webinar" },
  );
  assert.equal(waiting.find((stage) => stage.stage === "layout_review")?.status, "waiting");
});

test("online timeline marks layout_review done and starts the next row", () => {
  const view = pipelineTimeline(
    [
      { stage: "ingest", status: "succeeded" },
      { stage: "layout", status: "succeeded" },
      { stage: "asr", status: "succeeded", message: "Transcript ready" },
    ],
    null,
    { deliveryMode: "webinar", sessionStatus: "processing" },
  );
  assert.equal(view.find((stage) => stage.stage === "layout_review")?.status, "succeeded");
  assert.equal(view.find((stage) => stage.stage === "layout_review")?.detail, "by_you");
  assert.equal(view.find((stage) => stage.stage === "audio_features")?.status, "running");
});

test("content_llm stays one timeline step and shows chunk progress", () => {
  assert.equal(PIPELINE_STAGES.filter((stage) => stage === "content_llm").length, 1);
  assert.equal(pipelineStages("stage").filter((stage) => stage === "content_llm").length, 1);
  assert.equal(pipelineStages("webinar", "upload").filter((stage) => stage === "content_llm").length, 1);

  const event = parseProgressData(
    JSON.stringify({
      type: "stage",
      stage: "content_llm",
      status: "running",
      pct: 87.25,
      message: "outline 1/2",
    }),
  );
  assert.equal(event?.type, "stage");
  if (event?.type === "stage") {
    assert.equal(event.stage, "content_llm");
    assert.equal(event.pct, 87.25);
    assert.equal(event.message, "outline 1/2");
  }

  const running = pipelineTimeline(
    [{ stage: "content_llm", status: "running", message: "Reading the talk for content scores" }],
    { type: "stage", stage: "content_llm", status: "running", pct: 87.25, message: "outline 1/2" },
  );
  const rows = running.filter((stage) => stage.stage === "content_llm");
  assert.equal(rows.length, 1);
  assert.equal(rows[0]?.status, "running");
  assert.equal(rows[0]?.detail, "outline 1/2");
  assert.equal(running.some((stage) => stage.stage === "outline"), false);

  const done = pipelineTimeline(
    [
      {
        stage: "content_llm",
        status: "succeeded",
        message:
          "Content analysis stopped at the 8-minute budget after outline. Unfinished prompts stay N/A.",
      },
    ],
    null,
  );
  const content = done.find((stage) => stage.stage === "content_llm");
  assert.equal(content?.status, "succeeded");
  assert.match(content?.detail ?? "", /8-minute budget/);
  assert.match(content?.detail ?? "", /N\/A/);
  assert.equal(done.filter((stage) => stage.stage === "content_llm").length, 1);
});

test("legacy stage payloads without type still parse", () => {
  const event = parseProgressData(JSON.stringify({ stage: "asr", status: "succeeded" }));
  assert.equal(event?.type, "stage");
  if (event?.type === "stage") {
    assert.equal(event.stage, "asr");
  }
});
