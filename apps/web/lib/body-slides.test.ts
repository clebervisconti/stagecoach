import assert from "node:assert/strict";
import { test } from "node:test";
import {
  formatRatio,
  formatSeconds,
  heatMax,
  keyframeUrl,
  spaceCellOpacity,
  spacePeak,
  yawMax,
} from "./body-slides.ts";

test("heat and space helpers stay N/A-safe", () => {
  assert.equal(heatMax([]), 0.01);
  assert.equal(heatMax([{ t: 0, value: null }, { t: 1, value: 0.4 }]), 0.4);
  assert.equal(spacePeak([]), 0);
  assert.equal(spacePeak([0, 3, 1]), 3);
  assert.equal(spaceCellOpacity(0, 3), 0);
  assert.ok(spaceCellOpacity(3, 3) > spaceCellOpacity(1, 3));
});

test("yaw max and formatters do not invent zeros as scores", () => {
  assert.equal(yawMax([]), 0);
  assert.equal(formatRatio(null), null);
  assert.equal(formatRatio(0.25), "25%");
  assert.equal(formatSeconds(undefined), null);
  assert.equal(formatSeconds(2), "2.0 s");
  assert.equal(keyframeUrl("abc", 3), "/api/stagecoach/sessions/abc/keyframe?i=3");
});
