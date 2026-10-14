/** Body tab and Slides tab helpers (SPEC §8.7, issue #48). */

export type HeatPoint = { t: number; value: number | null };

export type SpaceDensity = {
  cols: number;
  rows: number;
  samples?: number;
  cells: number[];
  x_min?: number;
  x_max?: number;
  y_min?: number;
  y_max?: number;
};

export type BodyEvent = {
  type: string;
  t_start: number;
  t_end: number;
};

export type YawBin = {
  center: number;
  count: number;
  lo?: number;
  hi?: number;
};

export type BodyPayload = {
  available: boolean;
  duration_s: number;
  heat: HeatPoint[];
  space: SpaceDensity;
  events: BodyEvent[];
  sway: {
    value: number | null;
    unit?: string;
    applicable: boolean;
    failure_mode?: string | null;
  };
  yaw_histogram: YawBin[];
  audience_facing_ratio?: number | null;
  notes_down: BodyEvent[];
  expressivity: { available: boolean; opt_in?: boolean; points: HeatPoint[] };
  quality: {
    person_visible_ratio?: number | null;
    face_visible_ratio?: number | null;
    mean_face_height_px?: number | null;
    mean_person_height_px?: number | null;
    occlusion_ratio?: number | null;
    camera_setup?: { declared?: string; detected?: string; warning?: string | null };
  } | null;
};

export type SlideCard = {
  index: number;
  t_start: number | null;
  t_end: number | null;
  dwell_s: number | null;
  word_count: number;
  title: string;
  title_type: string | null;
  glance_level: number | null;
  reading_overlap: number | null;
  facing_screen_s: number | null;
  has_keyframe: boolean;
  suggested_title: string | null;
  suggestion_source: "ai" | "heuristic" | null;
};

export type SlidesPayload = {
  available: boolean;
  skip_reason?: string | null;
  slides: SlideCard[];
  ai_suggestions?: boolean;
};

export function heatMax(points: HeatPoint[]): number {
  const values = points.map((p) => p.value).filter((v): v is number => typeof v === "number");
  return values.length ? Math.max(...values, 0.01) : 0.01;
}

export function spaceCellOpacity(count: number, peak: number): number {
  if (peak <= 0 || count <= 0) return 0;
  return Math.min(0.85, 0.15 + (count / peak) * 0.7);
}

export function spacePeak(cells: number[]): number {
  return cells.reduce((max, n) => Math.max(max, n), 0);
}

export function yawMax(bins: YawBin[]): number {
  return bins.reduce((max, bin) => Math.max(max, bin.count), 0);
}

export function keyframeUrl(sessionId: string, index: number): string {
  return `/api/stagecoach/sessions/${sessionId}/keyframe?i=${encodeURIComponent(String(index))}`;
}

export function formatRatio(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return `${Math.round(value * 100)}%`;
}

export function formatSeconds(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return `${value.toFixed(1)} s`;
}
