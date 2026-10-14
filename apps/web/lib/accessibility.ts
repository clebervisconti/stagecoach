export const ACCESSIBILITY_KEYS = [
  "seated",
  "wheelchair",
  "limited_mobility",
  "one_handed",
  "speech_difference",
  "prefers_no_video_metrics",
  "low_vision",
] as const;

export type AccessibilityKey = (typeof ACCESSIBILITY_KEYS)[number];

export type AccessibilityProfile = Record<AccessibilityKey, boolean>;

export function emptyAccessibilityProfile(): AccessibilityProfile {
  return {
    seated: false,
    wheelchair: false,
    limited_mobility: false,
    one_handed: false,
    speech_difference: false,
    prefers_no_video_metrics: false,
    low_vision: false,
  };
}

export function normalizeAccessibility(raw: unknown): AccessibilityProfile {
  const src = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const out = emptyAccessibilityProfile();
  for (const key of ACCESSIBILITY_KEYS) {
    out[key] = src[key] === true;
  }
  if (out.wheelchair) {
    out.seated = true;
  }
  return out;
}
