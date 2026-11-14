import assert from "node:assert/strict";
import test from "node:test";
import { averageLast, drillTitle, greetingPart, numericScores, overallFinding } from "./overview.ts";

test("greeting follows the hour", () => {
  assert.equal(greetingPart(8), "morning");
  assert.equal(greetingPart(14), "afternoon");
  assert.equal(greetingPart(20), "evening");
});

test("scores ignore gaps and stay in date order", () => {
  const points = numericScores([
    { overall: null, created_at: "2026-11-02T00:00:00Z" },
    { overall: 74, created_at: "2026-11-12T00:00:00Z" },
    { overall: 61, created_at: "2026-11-08T00:00:00Z" },
  ]);
  assert.deepEqual(
    points.map((point) => point.overall),
    [61, 74],
  );
  assert.equal(averageLast(points, 3), 68);
});

test("a drill id becomes its title", () => {
  assert.equal(drillTitle("pause-instead-of-um"), "Pause instead of um");
  assert.equal(drillTitle("pace_ladder"), "Pace ladder");
});

test("finding text is measured and carries no private fields", () => {
  const text = overallFinding([
    { at: "2026-11-01", overall: 61 },
    { at: "2026-11-12", overall: 74 },
  ]);
  assert.equal(text, "Overall rose from 61 to 74 across 2 sessions");
  assert.equal(text?.includes("@"), false);
  assert.equal(text?.includes("/"), false);
});
