import assert from "node:assert/strict";
import test from "node:test";
import {
  cameraGaps,
  clusterMarkers,
  defaultZoom,
  filterCounts,
  isLongSession,
  matchesFilters,
  screenFlowView,
  virtualWindow,
  type ScreenSegment,
} from "./screen-flow.ts";

function segment(id: string, flags: string[] = []): ScreenSegment {
  const index = Number(id);
  return { id, t_start: index, t_end: index + 1, flags };
}

test("view states follow the screen payload", () => {
  assert.equal(screenFlowView({ deliveryMode: "stage" }), "hidden");
  assert.equal(screenFlowView({ deliveryMode: "webinar", loading: true }), "loading");
  assert.equal(screenFlowView({ deliveryMode: "webinar", error: true }), "error");
  assert.equal(screenFlowView({ deliveryMode: "webinar", sessionStatus: "processing" }), "processing");
  assert.equal(screenFlowView({ deliveryMode: "webinar", deckPages: 4 }), "deck");
  assert.equal(screenFlowView({ deliveryMode: "webinar" }), "empty");
  assert.equal(
    screenFlowView({
      deliveryMode: "recorded_video",
      payload: { segments: [segment("1")] },
    }),
    "ready",
  );
});

test("filters keep zero counts and match flags", () => {
  const segments = [segment("1", ["rushed"]), segment("2", ["silent_demo"]), segment("3")];
  const counts = filterCounts(segments);
  assert.equal(counts.all, 3);
  assert.equal(counts.rushed, 1);
  assert.equal(counts.long, 0);
  assert.equal(matchesFilters(segments[0], ["rushed", "silent"]), true);
  assert.equal(matchesFilters(segments[2], ["rushed"]), false);
  assert.equal(matchesFilters(segments[2], []), true);
});

test("virtual window stays within 24 rows for 300 screens", () => {
  const window = virtualWindow(300, 0, 800, 72);
  assert.ok(window.end - window.start <= 24);
  assert.ok(window.end <= 300);
  const later = virtualWindow(300, 72 * 200, 400, 72);
  assert.ok(later.end - later.start <= 24);
  assert.ok(later.start >= 190);
});

test("long sessions and the default zoom window", () => {
  assert.equal(isLongSession(300, 3600, 800), true);
  assert.equal(isLongSession(10, 600, 800, 30), false);
  assert.equal(isLongSession(10, 3600, 800, 1), true);
  const zoom = defaultZoom(3600, 900);
  assert.equal(zoom.width, 15 * 60);
  assert.ok(zoom.start <= 900);
  assert.ok(zoom.start + zoom.width >= 900);
});

test("markers cluster below 600px and camera gaps are the holes", () => {
  const groups = clusterMarkers(
    [
      { id: "a", kind: "deadAir", t: 10, dur_s: 4 },
      { id: "b", kind: "deadAir", t: 12, dur_s: 4 },
      { id: "c", kind: "prompt", t: 40, dur_s: 0 },
    ],
    390,
    100,
  );
  assert.equal(groups.length, 2);
  assert.equal(groups[0].length, 2);
  const gaps = cameraGaps(
    [
      { id: "s", t_start: 10, t_end: 20 },
      { id: "t", t_start: 40, t_end: 50 },
    ],
    60,
  );
  assert.deepEqual(gaps, [
    { t_start: 0, t_end: 10 },
    { t_start: 20, t_end: 40 },
    { t_start: 50, t_end: 60 },
  ]);
});
