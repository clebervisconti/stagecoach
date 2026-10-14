export const RETENTION_POLICIES = ["after_analysis", "days_30", "until_delete"] as const;

export type RetentionPolicy = (typeof RETENTION_POLICIES)[number];

export const DEFAULT_RETENTION_POLICY: RetentionPolicy = "days_30";

export function normalizeRetentionPolicy(raw: unknown): RetentionPolicy {
  if (raw === "after_analysis" || raw === "days_30" || raw === "until_delete") {
    return raw;
  }
  return DEFAULT_RETENTION_POLICY;
}
