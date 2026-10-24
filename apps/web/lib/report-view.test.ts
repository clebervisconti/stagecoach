import assert from "node:assert/strict";
import { test } from "node:test";
import { sampleReport } from "./fixtures/report-sample.ts";
import { categoryNaCopy } from "./na-copy.ts";
import { formatMeasured, metricLabel, metricUnusable } from "./metric-labels.ts";
import {
  formatOverallLine,
  goalRadarPoints,
  isSessionWideEvidence,
  keyMetricRows,
  overallHeadline,
  overallLevelWord,
  radarPoints,
  radarPolygon,
  slotTrafficLight,
} from "./report-view.ts";

test("overall headline is 71 ± 4 with partial coverage", () => {
  const headline = overallHeadline(sampleReport);
  assert.equal(headline.score, 71);
  assert.equal(headline.band, 4);
  assert.equal(headline.levelKey, "level4");
  assert.equal(headline.partial, true);
  assert.equal(formatOverallLine(71, 4, "Strong"), "71 ± 4 · Strong");
  assert.equal(overallLevelWord(true, "Strong", "Partial score"), "Partial score");
  assert.equal(overallLevelWord(false, "Strong", "Partial score"), "Strong");
});

test("session-wide metrics do not pretend to be a moment at 00:00", () => {
  assert.equal(
    isSessionWideEvidence({
      t_start: 0,
      text: "Speaking rate 140.0 words per minute.",
      metric_id: "pp_wpm",
    }),
    true,
  );
  assert.equal(isSessionWideEvidence({ t_start: 12.4, quote: "hello", text: "Core message" }), false);
});

test("metric labels carry units and the silence floor is not a measurement", () => {
  assert.equal(metricLabel("pq_integrated_lufs", "en"), "Integrated loudness");
  assert.equal(metricLabel("pq_clipping_ratio", "en"), "Clipping");
  assert.equal(metricLabel("va_glance_llm", "pt-BR"), "Teste de relance");
  assert.equal(formatMeasured(0.01, "ratio"), "1%");
  assert.equal(formatMeasured(-18.6, "LUFS"), "-18.6 LUFS");
  assert.equal(metricUnusable("pq_integrated_lufs", -70), true);
  assert.equal(metricUnusable("pq_integrated_lufs", -18.6), false);
});

test("a content-model failure is not the generic not-measured line", () => {
  const text = categoryNaCopy(
    {
      na_code: "not_applicable",
      na_reason: "The language model was unavailable, so this category stays N/A.",
    },
    (key) => key,
  );
  assert.equal(text, "na.model_unavailable");
});

test("unavailable pillars are gaps, never scored as zero", () => {
  const points = radarPoints(sampleReport);
  const visuals = points.find((point) => point.id === "visuals");
  const body = points.find((point) => point.id === "body");
  const voice = points.find((point) => point.id === "voice");
  assert.equal(visuals?.available, false);
  assert.equal(visuals?.score, null);
  assert.equal(body?.available, false);
  assert.equal(body?.score, null);
  assert.equal(voice?.available, true);
  assert.equal(voice?.score, 74);
  assert.notEqual(voice?.score, 0);

  const polygon = radarPolygon(points, 100, 0, 0);
  assert.equal(polygon.includes("0,0"), false);
  const vertexCount = polygon.trim() ? polygon.split(" ").length : 0;
  assert.equal(vertexCount, points.filter((point) => point.available).length);
});

test("goal radar points map category targets onto pillars", () => {
  const points = radarPoints(sampleReport);
  const goals = goalRadarPoints(points, [{ category_id: "fluency", target: 80 }]);
  const voice = goals.find((point) => point.id === "voice");
  assert.equal(voice?.available, true);
  assert.equal(voice?.score, 80);
  const polygon = radarPolygon(goals, 100, 0, 0);
  assert.ok(polygon.length > 0);
});

test("missing key metrics are labelled unavailable, not zero", () => {
  const rows = keyMetricRows(sampleReport);
  const facing = rows.find((row) => row.id === "ec_audience_facing_ratio");
  const fillers = rows.find((row) => row.id === "fl_filler_sounds_per_min");
  const slot = rows.find((row) => row.id === "tm_pct_of_slot");
  assert.equal(facing?.available, false);
  assert.equal(facing?.raw_value, null);
  assert.equal(facing?.formatted, null);
  assert.equal(fillers?.available, true);
  assert.equal(fillers?.formatted, "7.2");
  assert.equal(slot?.light, "green");
  assert.equal(slotTrafficLight(null), null);
});

test("N/A category scores stay null", () => {
  const visual = sampleReport.categories.find((category) => category.id === "visual_aids");
  assert.equal(visual?.applicable, false);
  assert.equal(visual?.score, null);
  assert.ok(visual?.na_reason);
});
