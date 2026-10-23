import assert from "node:assert/strict";
import { test } from "node:test";
import {
  applyRole,
  boxFromPoints,
  cloneLayout,
  draftsEqual,
  isLastCamera,
  mergeSegments,
  nudgeRegion,
  proposeMerge,
  resizeRegion,
  setWindow,
  splitSegment,
  type DraftSegment,
  type LayoutDraft,
} from "./layout-edit.ts";

function segment(index: number, start: number, end: number, regions: DraftSegment["regions"]): DraftSegment {
  return { index, t_start: start, t_end: end, kind: "composite", confidence: 0.9, regions };
}

function camera(id: string, x = 0.7): DraftSegment["regions"][number] {
  return { id, role: "camera", x, y: 0, w: 0.2, h: 0.3, source: "auto" };
}

function draft(segments: DraftSegment[], window: LayoutDraft["analysis_window"] = null, duration = 120): LayoutDraft {
  return { version: 1, segments, analysis_window: window, duration_s: duration };
}

test("nudge is one pixel of the preview and stays inside the frame", () => {
  const moved = nudgeRegion(camera("a", 0.5), -10, 0, 100, 50);
  assert.equal(moved.x, 0.4);
  assert.equal(moved.source, "user");
  const clamped = nudgeRegion(camera("a", 0), -10, -10, 100, 50);
  assert.equal(clamped.x, 0);
  assert.equal(clamped.y, 0);
});

test("resize keeps a five percent minimum", () => {
  const shrunk = resizeRegion(camera("a", 0.2), "se", -0.5, -0.5);
  assert.ok(shrunk.w >= 0.05);
  assert.ok(shrunk.h >= 0.05);
  const drawn = boxFromPoints({ x: 0.1, y: 0.1 }, { x: 0.12, y: 0.4 }, "screen", "d");
  assert.equal(drawn, null);
});

test("assigning camera demotes the previous camera to ignore", () => {
  const segments = [
    segment(0, 0, 120, [camera("a"), { id: "b", role: "ignore", x: 0.1, y: 0.5, w: 0.2, h: 0.2 }]),
  ];
  const next = applyRole(segments, 0, "b", "camera");
  assert.equal(next[0].regions.find((region) => region.id === "b")?.role, "camera");
  assert.equal(next[0].regions.find((region) => region.id === "a")?.role, "ignore");
});

test("last camera is the only camera box across segments", () => {
  const segments = [segment(0, 0, 60, [camera("a")]), segment(1, 60, 120, [camera("b")])];
  assert.equal(isLastCamera(segments, "a"), false);
  assert.equal(isLastCamera([segment(0, 0, 120, [camera("a")])], "a"), true);
});

test("split copies boxes onto the right and refuses an edge cut", () => {
  const segments = [segment(0, 0, 120, [camera("a")])];
  assert.equal(splitSegment(segments, 0, 0.4).ok, false);
  const split = splitSegment(segments, 0, 40);
  assert.equal(split.ok, true);
  if (!split.ok) return;
  assert.equal(split.segments.length, 2);
  assert.equal(split.segments[0].regions[0].id, "a");
  assert.notEqual(split.segments[1].regions[0].id, "a");
  assert.equal(split.segments[0].t_end, 40);
  assert.equal(split.segments[1].t_start, 40);
  assert.equal(split.segments[1].index, 1);
});

test("merge asks when boxes differ and keeps the chosen side", () => {
  const left = segment(0, 0, 60, [camera("a", 0.1)]);
  const right = segment(1, 60, 120, [camera("b", 0.7)]);
  assert.equal(proposeMerge([left, right], 1), "differ");
  assert.equal(proposeMerge([left, { ...right, regions: left.regions.map((region) => ({ ...region })) }], 1), "same");
  const kept = mergeSegments([left, right], 1, "right");
  assert.ok(kept);
  assert.equal(kept?.[0].t_start, 0);
  assert.equal(kept?.[0].t_end, 120);
  assert.equal(kept?.[0].regions[0].id, "b");
});

test("analysis window rejects under 60 seconds and clears when it covers the recording", () => {
  assert.deepEqual(setWindow(40, 0, 40), { ok: false, reason: "disabled" });
  assert.deepEqual(setWindow(120, 0, 50), { ok: false, reason: "short" });
  assert.deepEqual(setWindow(120, 0, 120), { ok: true, window: null });
  assert.deepEqual(setWindow(120, 10, 80), { ok: true, window: { start_s: 10, end_s: 80 } });
});

test("dirty compare ignores ids and preview metadata", () => {
  const base = cloneLayout({
    version: 2,
    frame: { duration_s: 120 },
    analysis_window: null,
    segments: [segment(0, 0, 120, [camera("a")])],
  });
  const renamed = cloneLayout({
    version: 2,
    frame: { duration_s: 120 },
    analysis_window: null,
    segments: [segment(0, 0, 120, [{ ...camera("other-id"), id: "zzz" }])],
  });
  assert.equal(draftsEqual(base, renamed), true);
  const moved = draft(renamed.segments.map((row) => ({ ...row, regions: [nudgeRegion(row.regions[0], -20, 0, 200, 100)] })));
  assert.equal(draftsEqual(base, moved), false);
  const trimmed = { ...base, analysis_window: { start_s: 0, end_s: 90 } };
  assert.equal(draftsEqual(base, trimmed), false);
});
