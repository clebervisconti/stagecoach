import assert from "node:assert/strict";
import { test } from "node:test";
import {
  DEFAULT_RETENTION_POLICY,
  RETENTION_POLICIES,
  normalizeRetentionPolicy,
} from "./retention.ts";

test("unknown or empty input is the 30-day default", () => {
  assert.equal(normalizeRetentionPolicy(null), DEFAULT_RETENTION_POLICY);
  assert.equal(normalizeRetentionPolicy("forever"), "days_30");
  assert.deepEqual(RETENTION_POLICIES, ["after_analysis", "days_30", "until_delete"]);
});

test("known policies pass through", () => {
  assert.equal(normalizeRetentionPolicy("after_analysis"), "after_analysis");
  assert.equal(normalizeRetentionPolicy("until_delete"), "until_delete");
});
