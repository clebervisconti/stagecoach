export const UI_CONSENT_PURPOSES = [
  "video_analysis",
  "expression_analysis",
  "keep_detailed_tracking",
] as const;

export type ConsentPurpose = (typeof UI_CONSENT_PURPOSES)[number];

export type ConsentItem = {
  purpose: string;
  granted: boolean;
  granted_at: string | null;
  revoked_at: string | null;
  version: string | null;
  title: string;
  what: string;
  why: string;
  limits: string;
  never: string;
};

export type ConsentsPayload = {
  policy_id: string;
  policy_version: string;
  locale: string;
  consents: ConsentItem[];
};

export function effectiveConsents(granted: Record<ConsentPurpose, boolean>): {
  video_analysis: boolean;
  expression_analysis: boolean;
  keep_detailed_tracking: boolean;
} {
  const video = Boolean(granted.video_analysis);
  return {
    video_analysis: video,
    expression_analysis: video && Boolean(granted.expression_analysis),
    keep_detailed_tracking: video && Boolean(granted.keep_detailed_tracking),
  };
}

export function itemByPurpose(payload: ConsentsPayload | null, purpose: ConsentPurpose): ConsentItem | null {
  return payload?.consents.find((item) => item.purpose === purpose) ?? null;
}
