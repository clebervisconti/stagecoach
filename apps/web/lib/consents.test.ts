import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { collectStrings, findForbiddenEmotionTerm } from "./forbidden-terms.ts";
import { effectiveConsents } from "./consents.ts";

test("expression and detailed tracking require video analysis", () => {
  const denied = effectiveConsents({
    video_analysis: false,
    expression_analysis: true,
    keep_detailed_tracking: true,
  });
  assert.equal(denied.video_analysis, false);
  assert.equal(denied.expression_analysis, false);
  assert.equal(denied.keep_detailed_tracking, false);

  const granted = effectiveConsents({
    video_analysis: true,
    expression_analysis: true,
    keep_detailed_tracking: false,
  });
  assert.equal(granted.video_analysis, true);
  assert.equal(granted.expression_analysis, true);
  assert.equal(granted.keep_detailed_tracking, false);
});

test("consent policy JSON does not use emotion-inference terms", () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const policy = JSON.parse(
    readFileSync(join(here, "..", "..", "..", "packages", "consent", "v1.json"), "utf8"),
  );
  for (const text of collectStrings(policy)) {
    const hit = findForbiddenEmotionTerm(text);
    assert.equal(hit, null, `consent policy uses forbidden term ${hit}: ${text}`);
  }
});
