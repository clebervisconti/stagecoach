import assert from "node:assert/strict";
import { test } from "node:test";
import {
  confidenceTone,
  formatBytes,
  formatClock,
  layoutComposition,
  pipelineStages,
  titleFromFilename,
} from "./online.ts";

test("titleFromFilename de-slugs a webinar export name", () => {
  assert.equal(titleFromFilename("q3-security-webinar.mp4"), "Q3 Security Webinar");
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
