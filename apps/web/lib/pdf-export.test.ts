import assert from "node:assert/strict";
import { test } from "node:test";
import { exportFileUrl, exportStatusUrl, exportUrl, PDF_SECTIONS, printPath } from "./pdf-export.ts";

test("PDF sections follow SPEC §8.9", () => {
  assert.deepEqual(PDF_SECTIONS, [
    "cover",
    "opportunities",
    "strengths",
    "categories",
    "time",
    "metrics",
    "drills",
    "methodology",
  ]);
});

test("export URLs stay on the BFF", () => {
  assert.equal(exportUrl("abc"), "/api/stagecoach/sessions/abc/export/pdf");
  assert.equal(exportStatusUrl("e1"), "/api/stagecoach/exports/e1");
  assert.equal(exportFileUrl("e1"), "/api/stagecoach/exports/e1/file");
  assert.equal(printPath("abc", false), "/sessions/abc/print");
  assert.equal(printPath("abc", true), "/sessions/abc/print?includeTranscript=1");
});
