/** Readiness from materials (SPEC §9.8 / issue #61). Categories 9–15 stay N/A until rehearsal. */

export const MATERIALS_CATEGORY_IDS = [
  "core_message",
  "structure",
  "storytelling",
  "audience_adaptation",
  "opening_close",
  "clarity",
  "impact",
  "visual_aids",
  "time_management",
  "qa",
] as const;

export const REHEARSAL_CATEGORY_IDS = [
  "pace_pausing",
  "vocal_variety",
  "fluency",
  "gestures_body",
  "eye_contact",
  "facial_affect",
  "energy_presence",
] as const;

export type ReadinessRow = {
  id: string;
  applicable: boolean;
  na_reason: string | null;
  ready: boolean;
};

export type PlanLike = {
  description?: string | null;
  goal?: string | null;
  slot_min?: number | null;
  outputs?: Record<string, unknown> | null;
};

const OUTPUT_HINT: Record<string, string[]> = {
  core_message: ["core_message", "cta"],
  structure: ["structure"],
  storytelling: ["outline", "structure"],
  audience_adaptation: ["audience"],
  opening_close: ["outline"],
  clarity: ["core_message"],
  impact: ["core_message"],
  visual_aids: ["slide_review"],
  time_management: ["time_budget", "cut_list"],
  qa: ["rehearsal_plan"],
};

function hasMaterial(plan: PlanLike, id: string): boolean {
  const outputs = plan.outputs || {};
  const keys = OUTPUT_HINT[id] || [];
  if (keys.some((key) => outputs[key] != null && outputs[key] !== "")) return true;
  if (id === "core_message" && plan.goal) return true;
  if (id === "time_management" && plan.slot_min) return true;
  if (plan.description) return true;
  return false;
}

export function readinessRows(plan: PlanLike): ReadinessRow[] {
  const materials = MATERIALS_CATEGORY_IDS.map((id) => ({
    id,
    applicable: true,
    na_reason: null,
    ready: hasMaterial(plan, id),
  }));
  const rehearsal = REHEARSAL_CATEGORY_IDS.map((id) => ({
    id,
    applicable: false,
    na_reason: "N/A until a rehearsal is recorded",
    ready: false,
  }));
  return [...materials, ...rehearsal];
}

export function topChanges(plan: PlanLike): { id: string; change: string; rewrite: string }[] {
  const rows: { id: string; change: string; rewrite: string }[] = [];
  const outputs = plan.outputs || {};
  if (!outputs.core_message && !plan.goal) {
    rows.push({
      id: "core_message",
      change: "Write a ≤ 15-word claim as the core message",
      rewrite: "One sentence the audience can repeat.",
    });
  }
  if (!outputs.structure) {
    rows.push({
      id: "structure",
      change: "Pick a structure (SCR for exec briefings)",
      rewrite: "Situation → Complication → Answer first.",
    });
  }
  if (!outputs.time_budget && !plan.slot_min) {
    rows.push({
      id: "time_budget",
      change: "Set the slot and a 90% speaking budget",
      rewrite: "20-min slot → 18 min speaking.",
    });
  }
  if (!outputs.outline) {
    rows.push({
      id: "outline",
      change: "Draft the storyline table",
      rewrite: "Section · purpose · story · ends at · minutes.",
    });
  }
  if (!outputs.rehearsal_plan) {
    rows.push({
      id: "rehearsal_plan",
      change: "Date a rehearsal plan backwards from the talk",
      rewrite: "Two timed run-throughs plus a recorded one.",
    });
  }
  return rows.slice(0, 3);
}
