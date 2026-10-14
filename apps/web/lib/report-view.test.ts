import assert from "node:assert/strict";
import { test } from "node:test";
import { sampleReport } from "./fixtures/report-sample.ts";
import {
  formatOverallLine,
  keyMetricRows,
  overallHeadline,
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

test("missing key metrics are labelled unavailable, not zero", () => {
  const rows = keyMetricRows(sampleReport);
  const facing = rows.find((row) => row.id === "audience_facing_ratio");
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
