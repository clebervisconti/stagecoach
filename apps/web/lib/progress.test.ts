import assert from "node:assert/strict";
import { test } from "node:test";
import { parseProgressData, shouldReloadReport } from "./progress.ts";

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

test("legacy stage payloads without type still parse", () => {
  const event = parseProgressData(JSON.stringify({ stage: "asr", status: "succeeded" }));
  assert.equal(event?.type, "stage");
  if (event?.type === "stage") {
    assert.equal(event.stage, "asr");
  }
});
