/** Delivery-mode helpers for the O1 wizard, layout review, and report. */

export const DELIVERY_MODES = ["stage", "webinar", "online_talk", "recorded_video"] as const;
export type DeliveryMode = (typeof DELIVERY_MODES)[number];
export type SourceKind = "upload" | "two_track" | "url";

export const LAST_MODE_KEY = "sc-last-delivery-mode";
export const LAST_CONTEXT_KEY = "sc-last-context-type";
export const DRAFT_KEY = "sc-new-session-draft";

export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024;
export const MAX_DURATION_SECONDS = 120 * 60;

export const CONTEXT_TYPES = [
  "keynote",
  "breakout",
  "exec_briefing",
  "sales_pitch",
  "virtual_meeting",
  "class_academic",
  "other",
] as const;

export type ContextType = (typeof CONTEXT_TYPES)[number];

export type LayoutRole = "camera" | "screen" | "ignore" | "other_participant";

export type LayoutRegion = {
  id: string;
  role: LayoutRole | string;
  x: number;
  y: number;
  w: number;
  h: number;
  confidence?: number;
};

export type LayoutSegment = {
  index: number;
  t_start: number;
  t_end: number;
  kind: string;
  confidence: number;
  regions: LayoutRegion[];
  preview_url?: string;
};

export type LayoutView = {
  session_id: string;
  job_id: string;
  version: number;
  status: string;
  confidence: number;
  detector_version: string;
  frame: { width?: number; height?: number; duration_s?: number };
  analysis_window?: { start_s: number; end_s: number } | null;
  review_reason?: string | null;
  preview_t?: number;
  auto_confirmed?: boolean;
  segments: LayoutSegment[];
};

export function isDeliveryMode(value: string | null | undefined): value is DeliveryMode {
  return Boolean(value && (DELIVERY_MODES as readonly string[]).includes(value));
}

export function titleFromFilename(name: string): string {
  const base = name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
  if (!base) return "";
  return base.replace(/\b\w/g, (ch) => ch.toUpperCase()).replace(/\b([A-Z])(\S*)/g, (full, first: string, rest: string) => {
    if (/^[A-Z0-9]{2,}$/.test(full)) return full;
    return first + rest.toLowerCase();
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = value >= 10 || unit === 0 ? 0 : 2;
  return `${value.toFixed(digits)} ${units[unit]}`;
}

/** Database timestamps are UTC. A value with no zone is not local time. */
export function parseServerInstant(value: string | null | undefined): number | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const zoned = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(trimmed);
  const parsed = Date.parse(zoned ? trimmed : `${trimmed}Z`);
  return Number.isFinite(parsed) ? parsed : null;
}

export function elapsedClock(startedAt: string | null | undefined, now = Date.now()): string {
  const start = parseServerInstant(startedAt);
  if (start == null) return "0:00";
  return formatClock((now - start) / 1000);
}

export function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function formatRange(start: number, end: number): string {
  return `${formatClock(start)}–${formatClock(end)}`;
}

export function spokenDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const parts: string[] = [];
  if (hours) parts.push(`${hours} hour${hours === 1 ? "" : "s"}`);
  if (minutes) parts.push(`${minutes} minute${minutes === 1 ? "" : "s"}`);
  if (!hours && (secs || !parts.length)) parts.push(`${secs} second${secs === 1 ? "" : "s"}`);
  return parts.join(" ");
}

export function spokenBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} gigabytes`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} megabytes`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} kilobytes`;
  return `${bytes} bytes`;
}

export type ConfidenceTone = "high" | "check" | "unsure" | "empty";

export function confidenceTone(
  confidence: number,
  reviewReason?: string | null,
  segmentConfidences: number[] = [],
): ConfidenceTone {
  if (reviewReason === "no_regions_found") return "empty";
  if (confidence < 0.5) return "unsure";
  const lowSegment = segmentConfidences.some((value) => value < 0.6);
  if (
    confidence < 0.8 ||
    lowSegment ||
    reviewReason === "camera_tile_low_confidence" ||
    reviewReason === "screen_region_unclear"
  ) {
    return "check";
  }
  return "high";
}

export function segmentRoles(segment: LayoutSegment | undefined): LayoutRole[] {
  if (!segment) return [];
  const seen = new Set<LayoutRole>();
  for (const region of segment.regions || []) {
    if (region.role === "camera" || region.role === "screen" || region.role === "ignore" || region.role === "other_participant") {
      seen.add(region.role);
    }
  }
  return (["camera", "screen", "other_participant", "ignore"] as const).filter((role) => seen.has(role));
}

export type LayoutComposition = "camera_screen" | "camera" | "screen" | "audio";

export function layoutComposition(segment: LayoutSegment | undefined): LayoutComposition {
  const roles = new Set(segmentRoles(segment));
  if (roles.has("camera") && roles.has("screen")) return "camera_screen";
  if (roles.has("camera")) return "camera";
  if (roles.has("screen")) return "screen";
  return "audio";
}

export type LayoutSummary = {
  dominant: LayoutComposition;
  cameraSegments: number;
  segmentCount: number;
  mixed: boolean;
};

/** Dominant layout by time on screen, plus how often the camera shows up. */
export function summariseLayouts(segments: LayoutSegment[]): LayoutSummary {
  const spans: Record<LayoutComposition, number> = { camera_screen: 0, camera: 0, screen: 0, audio: 0 };
  const counts: Record<LayoutComposition, number> = { camera_screen: 0, camera: 0, screen: 0, audio: 0 };
  let cameraSegments = 0;
  for (const segment of segments) {
    const composition = layoutComposition(segment);
    spans[composition] += Math.max(0, segment.t_end - segment.t_start);
    counts[composition] += 1;
    if (composition === "camera" || composition === "camera_screen") cameraSegments += 1;
  }
  const ranked = (Object.keys(spans) as LayoutComposition[]).sort((a, b) => {
    if (spans[b] !== spans[a]) return spans[b] - spans[a];
    return counts[b] - counts[a];
  });
  const dominant = ranked[0] ?? "audio";
  return {
    dominant,
    cameraSegments,
    segmentCount: segments.length,
    mixed: ranked.filter((key) => counts[key] > 0).length > 1,
  };
}

export function regionPositionWords(region: LayoutRegion): { position: string; size: string } {
  const cx = region.x + region.w / 2;
  const cy = region.y + region.h / 2;
  const vertical = cy < 0.33 ? "top" : cy > 0.66 ? "bottom" : "middle";
  const horizontal = cx < 0.33 ? "left" : cx > 0.66 ? "right" : "centre";
  const position = vertical === "middle" && horizontal === "centre" ? "centre" : `${vertical} ${horizontal}`;
  const size =
    region.w >= 0.7 ? "about three quarters of the width" : region.w >= 0.4 ? "about half of the width" : "about a fifth of the width";
  return { position, size };
}

export function readLastMode(): DeliveryMode | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(LAST_MODE_KEY);
  return isDeliveryMode(value) ? value : null;
}

export function writeLastMode(mode: DeliveryMode): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LAST_MODE_KEY, mode);
}

export function readLastContext(): ContextType | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(LAST_CONTEXT_KEY);
  return (CONTEXT_TYPES as readonly string[]).includes(value || "") ? (value as ContextType) : null;
}

export function writeLastContext(context: ContextType): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LAST_CONTEXT_KEY, context);
}

export const STAGE_PIPELINE = [
  "ingest",
  "asr",
  "alignment",
  "audio_features",
  "partial_scoring",
  "vision",
  "slides",
  "content_llm",
  "fusion_scoring",
  "report",
] as const;

export const ONLINE_PIPELINE = [
  "ingest",
  "layout",
  "layout_review",
  "asr",
  "audio_features",
  "production_quality",
  "partial_scoring",
  "region_crops",
  "vision",
  "slides",
  "content_llm",
  "fusion_scoring",
  "report",
] as const;

export function pipelineStages(deliveryMode: string = "stage", sourceKind: string = "upload"): readonly string[] {
  if (deliveryMode === "stage") return STAGE_PIPELINE;
  const stages: string[] = [...ONLINE_PIPELINE];
  if (sourceKind === "two_track") {
    stages.splice(1, 0, "sync");
  }
  return stages;
}

export const NA_CODES = [
  "not_in_phase",
  "consent_video_off",
  "vision_unavailable",
  "camera_not_visible",
  "camera_too_small",
  "audio_only_chosen",
  "audio_only_media",
  "no_screen",
  "qa_not_detected",
  "qa_declared_none",
  "target_length_missing",
  "insufficient_speech",
  "hands_not_visible",
  "stage_mode",
  "no_slides",
  "model_unavailable",
  "camera_coverage_low",
  "not_applicable",
] as const;

export type NaCode = (typeof NA_CODES)[number];

export function isNaCode(value: string | null | undefined): value is NaCode {
  return Boolean(value && (NA_CODES as readonly string[]).includes(value));
}
