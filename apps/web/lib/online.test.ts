import assert from "node:assert/strict";
import { test } from "node:test";
import {
  confidenceTone,
  elapsedClock,
  formatBytes,
  formatClock,
  layoutComposition,
  parseServerInstant,
  pipelineStages,
  summariseLayouts,
  titleFromFilename,
} from "./online.ts";

test("titleFromFilename de-slugs a webinar export name", () => {
  assert.equal(titleFromFilename("q3-security-webinar.mp4"), "Q3 Security Webinar");
});

test("a timezone-less server timestamp is UTC, so elapsed time is not stuck at 0:00", () => {
  const now = Date.parse("2026-10-24T15:00:00Z");
  assert.equal(parseServerInstant("2026-10-24T14:58:30"), Date.parse("2026-10-24T14:58:30Z"));
  assert.equal(elapsedClock("2026-10-24T14:58:30", now), "1:30");
  assert.equal(elapsedClock("2026-10-24T14:58:30Z", now), "1:30");
});

test("formatBytes and formatClock match the design examples", () => {
  assert.equal(formatBytes(1.24 * 1024 * 1024 * 1024), "1.24 GB");
  assert.equal(formatClock(58 * 60 + 12), "58:12");
  assert.equal(formatClock(12 * 60 + 40), "12:40");
});

test("confidenceTone maps HIGH / CHECK THIS / NOT SURE / empty", () => {
  assert.equal(confidenceTone(0.86), "high");
  assert.equal(confidenceTone(0.72), "check");
  assert.equal(confidenceTone(0.86, "camera_tile_low_confidence"), "check");
  assert.equal(confidenceTone(0.4), "unsure");
  assert.equal(confidenceTone(0.9, "no_regions_found"), "empty");
});

test("layoutComposition reads camera and screen roles", () => {
  assert.equal(
    layoutComposition({
      index: 0,
      t_start: 0,
      t_end: 10,
      kind: "composite",
      confidence: 0.9,
      regions: [
        { id: "r0", role: "camera", x: 0.8, y: 0, w: 0.2, h: 0.2 },
        { id: "r1", role: "screen", x: 0, y: 0, w: 0.8, h: 1 },
      ],
    }),
    "camera_screen",
  );
});

test("the layout headline follows the whole timeline, not only the first segment", () => {
  const screen = {
    index: 0,
    t_start: 0,
    t_end: 20,
    kind: "screen_full",
    confidence: 0.9,
    regions: [{ id: "r0", role: "screen" as const, x: 0, y: 0, w: 1, h: 1 }],
  };
  const camera = {
    index: 1,
    t_start: 20,
    t_end: 400,
    kind: "camera_full",
    confidence: 0.9,
    regions: [{ id: "r1", role: "camera" as const, x: 0, y: 0, w: 1, h: 1 }],
  };
  const summary = summariseLayouts([screen, camera]);
  assert.equal(layoutComposition(screen), "screen");
  assert.equal(summary.mixed, true);
  assert.equal(summary.dominant, "camera");
  assert.equal(summary.cameraSegments, 1);
  assert.equal(summary.segmentCount, 2);
  const single = summariseLayouts([
    {
      index: 0,
      t_start: 0,
      t_end: 540,
      kind: "composite",
      confidence: 0.9,
      regions: [
        { id: "r0", role: "camera" as const, x: 0.8, y: 0, w: 0.2, h: 0.2 },
        { id: "r1", role: "screen" as const, x: 0, y: 0, w: 0.8, h: 1 },
      ],
    },
  ]);
  assert.equal(single.mixed, false);
  assert.equal(single.dominant, "camera_screen");
});

test("pipelineStages keeps stage order and folds alignment for online", () => {
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
  const online = pipelineStages("webinar", "upload");
  assert.equal(online.includes("alignment"), false);
  assert.equal(online.includes("layout"), true);
  assert.equal(online.includes("production_quality"), true);
  assert.equal(online.includes("sync"), false);
  assert.equal(pipelineStages("webinar", "two_track").includes("sync"), true);
});
