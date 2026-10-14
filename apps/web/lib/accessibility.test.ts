import assert from "node:assert/strict";
import { test } from "node:test";
import { normalizeAccessibility } from "./accessibility.ts";

test("wheelchair implies seated and drops unknown keys", () => {
  const profile = normalizeAccessibility({ wheelchair: true, extra: true });
  assert.equal(profile.wheelchair, true);
  assert.equal(profile.seated, true);
  assert.equal(profile.limited_mobility, false);
  assert.equal("extra" in profile, false);
});

test("empty input is all false", () => {
  const profile = normalizeAccessibility(null);
  assert.equal(profile.prefers_no_video_metrics, false);
  assert.equal(profile.one_handed, false);
});
