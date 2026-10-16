export const CONTEXT_TYPES = [
  "keynote",
  "breakout",
  "exec_briefing",
  "sales_pitch",
  "virtual_meeting",
  "class_academic",
  "other",
] as const;

export const PLAN_FORM_FIELDS = [
  "title",
  "context_type",
  "description",
  "audience_roles",
  "audience_seniority",
  "audience_depth",
  "audience_size",
  "audience_language",
  "audience_know",
  "audience_care",
  "audience_objections",
  "audience_decision",
  "goal",
  "slot_min",
  "qa_in_slot",
  "qa_min",
  "late_start",
  "delivery_format",
  "language",
  "known_habits",
  "must_include",
] as const;

export function buildPlanPayload(form: FormData): Record<string, unknown> {
  const depth = Number(form.get("audience_depth") || 0);
  return {
    title: String(form.get("title") || ""),
    context_type: String(form.get("context_type") || "exec_briefing"),
    description: String(form.get("description") || "").slice(0, 4000),
    goal: String(form.get("goal") || "") || null,
    slot_min: form.get("slot_min") ? Number(form.get("slot_min")) : null,
    qa_in_slot: form.get("qa_in_slot") === "on",
    qa_min: form.get("qa_min") ? Number(form.get("qa_min")) : null,
    language: String(form.get("language") || "en"),
    delivery_format: String(form.get("delivery_format") || "") || null,
    must_include: String(form.get("must_include") || "") || null,
    known_habits: String(form.get("known_habits") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    audience: {
      roles: String(form.get("audience_roles") || "") || null,
      seniority: String(form.get("audience_seniority") || "") || null,
      technical_depth: depth || null,
      size: String(form.get("audience_size") || "") || null,
      language: String(form.get("audience_language") || "") || null,
      already_know: String(form.get("audience_know") || "") || null,
      care: String(form.get("audience_care") || "") || null,
      objections: String(form.get("audience_objections") || "") || null,
      decision: String(form.get("audience_decision") || "") || null,
    },
    constraints: {
      late_start: form.get("late_start") === "on",
    },
  };
}
