/** Screen & flow view model. Pure functions so node:test can cover the tab. */

export type FlowFilter = "long" | "rushed" | "silent" | "talkOver";

export type ScreenSegment = {
  id: string;
  index?: number;
  t_start: number;
  t_end: number;
  dwell_s?: number;
  type?: string;
  keyframe_url?: string | null;
  ocr_word_count?: number;
  flags?: string[];
  narration?: {
    shared_terms?: string[];
    aligned?: boolean;
    first_mention_s?: number | null;
  };
  transition_in?: {
    clean?: boolean;
    nearest_pause_s?: number | null;
    signpost?: boolean;
    t?: number;
  } | null;
  deck_page?: number | null;
};

export type FlowEvent = {
  id?: string;
  kind: string;
  t: number;
  dur_s?: number;
};

export type FlowMetric = {
  id: string;
  value?: number | null;
  applicable?: boolean;
  unit?: string;
};

export type FlowCoaching = {
  source?: string | null;
  fallback?: boolean;
  prompt_version?: string | null;
  observations?: { title: string; detail?: string; t?: number; evidence_ids?: string[] }[];
  drills?: { title: string; how?: string; practice_time_min?: number; targets_metric?: string }[];
  strengths?: { title: string; evidence_ids?: string[] }[];
};

export type ScreenDocument = {
  delivery_mode?: string;
  screen_visible_s?: number;
  duration_s?: number;
  segments?: ScreenSegment[];
  events?: FlowEvent[];
  metrics?: FlowMetric[];
  coaching?: FlowCoaching | null;
  deck_only?: boolean;
};

export type ScreenFlowView = "hidden" | "loading" | "processing" | "error" | "empty" | "deck" | "ready";

export type FlowStep = { stage: string; status: string };

const VIRTUAL_CAP = 24;
export const ZOOM_MINUTES = [5, 15, 30, 60] as const;

export function screenFlowView(input: {
  deliveryMode?: string | null;
  loading?: boolean;
  error?: boolean;
  payload?: ScreenDocument | null;
  steps?: FlowStep[];
  sessionStatus?: string | null;
  deckPages?: number;
}): ScreenFlowView {
  if (!input.deliveryMode || input.deliveryMode === "stage") return "hidden";
  const payload = input.payload;
  const segments = payload?.segments ?? [];
  if (!payload || segments.length === 0) {
    if (input.loading) return "loading";
    if (input.error) return "error";
    const screen = (input.steps ?? []).find((step) => step.stage === "screen_flow");
    const running = screen && (screen.status === "running" || screen.status === "pending");
    const processing = input.sessionStatus === "processing" || input.sessionStatus === "running";
    if (running || processing) return "processing";
    if ((input.deckPages ?? 0) > 0 || payload?.deck_only) return "deck";
    return "empty";
  }
  return "ready";
}

export function metricValue(metrics: FlowMetric[] | undefined, id: string): number | null {
  const row = (metrics ?? []).find((item) => item.id === id);
  if (!row || row.applicable === false || row.value == null || Number.isNaN(row.value)) return null;
  return row.value;
}

export function flagSet(segment: ScreenSegment): Set<string> {
  return new Set((segment.flags ?? []).map((flag) => flag.toLowerCase()));
}

export function matchesFilters(segment: ScreenSegment, filters: FlowFilter[]): boolean {
  if (filters.length === 0) return true;
  const flags = flagSet(segment);
  return filters.some((filter) => {
    if (filter === "long") return flags.has("static_long") || flags.has("long");
    if (filter === "rushed") return flags.has("rushed");
    if (filter === "silent") return flags.has("silent_demo") || [...flags].some((flag) => flag.startsWith("silent"));
    return flags.has("talk_over_transition") || flags.has("talk_over") || [...flags].some((flag) => flag.includes("talk"));
  });
}

export function filterCounts(segments: ScreenSegment[]): Record<"all" | FlowFilter, number> {
  return {
    all: segments.length,
    long: segments.filter((segment) => matchesFilters(segment, ["long"])).length,
    rushed: segments.filter((segment) => matchesFilters(segment, ["rushed"])).length,
    silent: segments.filter((segment) => matchesFilters(segment, ["silent"])).length,
    talkOver: segments.filter((segment) => matchesFilters(segment, ["talkOver"])).length,
  };
}

export function virtualWindow(
  count: number,
  scrollTop: number,
  viewport: number,
  rowHeight: number,
): { start: number; end: number } {
  if (count <= 0) return { start: 0, end: 0 };
  const height = Math.max(rowHeight, 1);
  const start = Math.max(0, Math.floor(scrollTop / height) - 2);
  const visible = Math.ceil(Math.max(viewport, height) / height) + 4;
  const span = Math.min(VIRTUAL_CAP, visible, count);
  const cappedStart = Math.min(start, Math.max(0, count - span));
  return { start: cappedStart, end: cappedStart + span };
}

export function isLongSession(screenCount: number, durationS: number, stripWidthPx: number, minBlockS = 0): boolean {
  if (screenCount > 120) return true;
  if (stripWidthPx <= 0 || durationS <= 0 || minBlockS <= 0) return false;
  return (minBlockS / durationS) * stripWidthPx < 2;
}

export function defaultZoom(durationS: number, firstFlagS: number | null): { start: number; width: number } {
  const width = Math.min(15 * 60, Math.max(durationS, 1));
  const anchor = firstFlagS ?? 0;
  const start = Math.max(0, Math.min(anchor - width / 2, Math.max(0, durationS - width)));
  return { start, width };
}

export type FlowMarker = {
  id: string;
  kind: "talkOver" | "deadAir" | "silentDemo" | "prompt";
  t: number;
  dur_s: number;
  screenId?: string;
};

export function markersFor(document: ScreenDocument): FlowMarker[] {
  const markers: FlowMarker[] = [];
  for (const event of document.events ?? []) {
    const kind = event.kind;
    const mapped =
      kind === "talk_over" || kind === "talk_over_transition"
        ? "talkOver"
        : kind === "dead_air"
          ? "deadAir"
          : kind === "silent_demo"
            ? "silentDemo"
            : kind === "interaction_prompt"
              ? "prompt"
              : null;
    if (!mapped) continue;
    markers.push({
      id: event.id || `${mapped}-${event.t}`,
      kind: mapped,
      t: event.t,
      dur_s: event.dur_s ?? 0,
    });
  }
  return markers;
}

export function clusterMarkers(markers: FlowMarker[], widthPx: number, durationS: number): FlowMarker[][] {
  if (widthPx >= 600 || durationS <= 0 || markers.length === 0) return markers.map((marker) => [marker]);
  const ordered = [...markers].sort((a, b) => a.t - b.t);
  const groups: FlowMarker[][] = [];
  for (const marker of ordered) {
    const last = groups[groups.length - 1];
    if (!last) {
      groups.push([marker]);
      continue;
    }
    const gap = Math.abs(marker.t - last[0].t) / durationS;
    if (gap < 0.04 && marker.kind === last[0].kind) last.push(marker);
    else groups.push([marker]);
  }
  return groups;
}

export type CameraGap = { t_start: number; t_end: number };

export function cameraGaps(segments: ScreenSegment[], durationS: number): CameraGap[] {
  const ordered = [...segments].sort((a, b) => a.t_start - b.t_start);
  const gaps: CameraGap[] = [];
  let cursor = 0;
  for (const segment of ordered) {
    if (segment.t_start > cursor + 0.05) gaps.push({ t_start: cursor, t_end: segment.t_start });
    cursor = Math.max(cursor, segment.t_end);
  }
  if (durationS > cursor + 0.05) gaps.push({ t_start: cursor, t_end: durationS });
  return gaps;
}

export function screenTime(document: ScreenDocument): number {
  if (typeof document.screen_visible_s === "number") return document.screen_visible_s;
  return (document.segments ?? []).reduce((sum, segment) => sum + Math.max(0, segment.t_end - segment.t_start), 0);
}
