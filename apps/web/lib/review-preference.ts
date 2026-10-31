export const REVIEW_LAYOUTS = ["always", "when_unsure", "never"] as const;
export type ReviewLayout = (typeof REVIEW_LAYOUTS)[number];

export function normalizeReviewLayout(value: unknown): ReviewLayout {
  if (value === "always" || value === "when_unsure" || value === "never") return value;
  return "when_unsure";
}
