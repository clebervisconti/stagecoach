import assert from "node:assert/strict";
import test from "node:test";
import { CONTEXT_TYPES, PLAN_FORM_FIELDS, buildPlanPayload } from "./prep-form.ts";

test("plan form lists §9.1 fields", () => {
  for (const field of [
    "title",
    "context_type",
    "description",
    "goal",
    "slot_min",
    "qa_in_slot",
    "language",
    "must_include",
    "audience_decision",
  ]) {
    assert.ok(PLAN_FORM_FIELDS.includes(field as (typeof PLAN_FORM_FIELDS)[number]));
  }
  assert.ok(CONTEXT_TYPES.includes("exec_briefing"));
});

test("payload caps description and nests audience", () => {
  const form = new FormData();
  form.set("title", "Board update");
  form.set("context_type", "exec_briefing");
  form.set("description", "x".repeat(5000));
  form.set("audience_decision", "approve the pilot");
  form.set("audience_depth", "3");
  form.set("slot_min", "20");
  const payload = buildPlanPayload(form);
  assert.equal((payload.description as string).length, 4000);
  assert.equal((payload.audience as { decision: string }).decision, "approve the pilot");
  assert.equal(payload.slot_min, 20);
});
