import assert from "node:assert/strict";
import test from "node:test";
import { normalizeReviewLayout } from "./review-preference.ts";

test("review layout falls back to when unsure", () => {
  assert.equal(normalizeReviewLayout("always"), "always");
  assert.equal(normalizeReviewLayout("never"), "never");
  assert.equal(normalizeReviewLayout("when_unsure"), "when_unsure");
  assert.equal(normalizeReviewLayout(null), "when_unsure");
  assert.equal(normalizeReviewLayout("sometimes"), "when_unsure");
});
