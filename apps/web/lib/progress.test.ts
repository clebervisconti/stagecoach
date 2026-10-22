import assert from "node:assert/strict";
import { test } from "node:test";
import { parseProgressData, pipelineStages, pipelineTimeline, shouldReloadReport, stageProblem } from "./progress.ts";

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

test("legacy stage payloads without type still parse", () => {
  const event = parseProgressData(JSON.stringify({ stage: "asr", status: "succeeded" }));
  assert.equal(event?.type, "stage");
  if (event?.type === "stage") {
    assert.equal(event.stage, "asr");
  }
});
