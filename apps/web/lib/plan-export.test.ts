import assert from "node:assert/strict";
import test from "node:test";
import { EDITOR_SECTIONS, downloadMarkdown, planToMarkdown } from "./plan-export.ts";

test("markdown export includes header, readiness, and top changes", () => {
  const md = planToMarkdown({
    title: "Board update",
    context_type: "exec_briefing",
    slot_min: 20,
    language: "en",
    audience: { roles: "executives" },
    goal: "Approve the pilot",
  });
  assert.match(md, /Board update/);
  assert.match(md, /exec_briefing/);
  assert.match(md, /## Readiness/);
  assert.match(md, /N\/A until a rehearsal/);
  assert.match(md, /## Top 3 changes/);
  const file = downloadMarkdown({ title: "Board update" });
  assert.equal(file.filename, "board-update.md");
});

test("editor sections cover the prep outputs", () => {
  for (const section of ["core_message", "structure", "outline", "time_budget", "rehearsal_plan"]) {
    assert.ok(EDITOR_SECTIONS.includes(section as (typeof EDITOR_SECTIONS)[number]));
  }
});
