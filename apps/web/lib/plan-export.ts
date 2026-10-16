import { readinessRows, topChanges, type PlanLike } from "./plan-readiness.ts";

export const EDITOR_SECTIONS = [
  "core_message",
  "audience",
  "structure",
  "outline",
  "slide_review",
  "time_budget",
  "cut_list",
  "rehearsal_plan",
  "objectives",
] as const;

export type EditorSection = (typeof EDITOR_SECTIONS)[number];

export type PlanRecord = PlanLike & {
  id?: string;
  title?: string;
  context_type?: string;
  audience?: Record<string, unknown> | null;
  slot_min?: number | null;
  language?: string | null;
  outputs?: Record<string, unknown> | null;
};

export function sectionText(plan: PlanRecord, section: EditorSection): string {
  const outputs = plan.outputs || {};
  const value = outputs[section];
  if (value == null) return "";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

export function planToMarkdown(plan: PlanRecord): string {
  const audience = plan.audience || {};
  const lines = [
    `# ${plan.title || "Untitled plan"}`,
    "",
    `${plan.context_type || "other"} · ${audience.roles || "audience n/a"} · ${plan.slot_min ?? "?"} min · ${plan.language || "en"}`,
    "",
    "## Core message",
    sectionText(plan, "core_message") || plan.goal || "(not set)",
    "",
    "## Structure",
    sectionText(plan, "structure") || "(not set)",
    "",
    "## Outline",
    sectionText(plan, "outline") || "(not set)",
    "",
    "## Time budget",
    sectionText(plan, "time_budget") || (plan.slot_min ? `${plan.slot_min} min slot` : "(not set)"),
    "",
    "## Cut list",
    sectionText(plan, "cut_list") || "(not set)",
    "",
    "## Slide review",
    sectionText(plan, "slide_review") || "(not set)",
    "",
    "## Rehearsal plan",
    sectionText(plan, "rehearsal_plan") || "(not set)",
    "",
    "## Readiness",
    ...readinessRows(plan).map((row) =>
      row.applicable
        ? `- ${row.id}: ${row.ready ? "ready from materials" : "needs work"}`
        : `- ${row.id}: ${row.na_reason}`,
    ),
    "",
    "## Top 3 changes",
    ...topChanges(plan).map((row, index) => `${index + 1}. ${row.change} — ${row.rewrite}`),
    "",
  ];
  return lines.join("\n");
}

export function downloadMarkdown(plan: PlanRecord): { filename: string; body: string } {
  const slug = (plan.title || "plan").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return { filename: `${slug || "plan"}.md`, body: planToMarkdown(plan) };
}
