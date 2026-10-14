/** Video-synced timeline helpers (SPEC §8.4, issue #47). */

export const TIMELINE_LANE_IDS = [
  "sections",
  "slides",
  "fillers",
  "long_pauses",
  "rushing",
  "monotone",
  "gestures",
  "audience_facing",
  "smiles",
  "clt_story",
  "qa",
] as const;

export type TimelineLaneId = (typeof TIMELINE_LANE_IDS)[number];

export type TimelineItem = {
  t_start: number;
  t_end: number;
  label: string;
  kind: string;
};

export type TimelineLane = {
  id: TimelineLaneId | string;
  available: boolean;
  opt_in?: boolean;
  default_on?: boolean;
  items: TimelineItem[];
};

export type TimelinePayload = {
  duration_s: number;
  sprite_interval_s?: number;
  sprite_count?: number;
  lanes: TimelineLane[];
};

export function playheadPercent(current: number, duration: number): number {
  if (!Number.isFinite(duration) || duration <= 0) return 0;
  const t = Number.isFinite(current) ? Math.max(0, current) : 0;
  return Math.min(100, (t / duration) * 100);
}

export function timeFromClick(clientX: number, rect: { left: number; width: number }, duration: number): number {
  if (!Number.isFinite(duration) || duration <= 0 || rect.width <= 0) return 0;
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  return ratio * duration;
}

export function spriteUrl(sessionId: string, t: number): string {
  const safe = Number.isFinite(t) && t > 0 ? t : 0;
  return `/api/stagecoach/sessions/${sessionId}/sprite?t=${encodeURIComponent(String(Math.floor(safe)))}`;
}

export function laneMarkers(lane: TimelineLane | undefined): Array<{ id: string; t: number }> {
  if (!lane) return [];
  return lane.items.map((item, index) => ({
    id: `${lane.id}-${index}`,
    t: item.t_start,
  }));
}

export function defaultEnabledLanes(payload: TimelinePayload | null): Set<string> {
  const enabled = new Set<string>();
  for (const lane of payload?.lanes ?? []) {
    if (lane.available && lane.default_on !== false && lane.id !== "smiles") {
      enabled.add(lane.id);
    }
    if (lane.id === "smiles" && lane.available && lane.default_on) {
      enabled.add(lane.id);
    }
  }
  return enabled;
}

export function itemAtTime(lane: TimelineLane, t: number): TimelineItem | null {
  return (
    lane.items.find((item) => t >= item.t_start - 0.05 && t <= item.t_end + 0.05) ?? null
  );
}
