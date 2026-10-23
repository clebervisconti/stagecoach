/** Pure layout-editor math. Coordinates stay 0–1. Nudges are pixels of the preview. */

import type { LayoutRegion, LayoutSegment, LayoutView } from "./online.ts";

export const MIN_REGION = 0.05;
export const MIN_WINDOW_S = 60;
export const EDGE_SPLIT_S = 1;

export const EDITOR_ROLES = ["camera", "screen", "other_participant", "ignore"] as const;
export type EditorRole = (typeof EDITOR_ROLES)[number];
export type Corner = "nw" | "ne" | "sw" | "se";
export type MergeKeep = "left" | "right";

export type DraftRegion = {
  id: string;
  role: EditorRole | string;
  x: number;
  y: number;
  w: number;
  h: number;
  confidence?: number;
  source?: "auto" | "user";
};

export type DraftSegment = {
  index: number;
  t_start: number;
  t_end: number;
  kind: string;
  confidence: number;
  regions: DraftRegion[];
  preview_url?: string;
};

export type DraftWindow = { start_s: number; end_s: number } | null;

export type LayoutDraft = {
  version: number;
  segments: DraftSegment[];
  analysis_window: DraftWindow;
  duration_s: number;
};

let regionSerial = 0;

export function newRegionId(): string {
  regionSerial += 1;
  const rand = Math.random().toString(36).slice(2, 6);
  return `u${regionSerial.toString(36)}${rand}`;
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000;
}

function cloneRegion(region: LayoutRegion | DraftRegion): DraftRegion {
  return {
    id: region.id,
    role: region.role,
    x: region.x,
    y: region.y,
    w: region.w,
    h: region.h,
    confidence: region.confidence,
    source: "source" in region && region.source ? region.source : "auto",
  };
}

function cloneSegment(segment: LayoutSegment | DraftSegment): DraftSegment {
  return {
    index: segment.index,
    t_start: segment.t_start,
    t_end: segment.t_end,
    kind: segment.kind,
    confidence: segment.confidence,
    regions: (segment.regions || []).map(cloneRegion),
    preview_url: segment.preview_url,
  };
}

export function cloneLayout(view: Pick<LayoutView, "version" | "segments" | "analysis_window" | "frame">): LayoutDraft {
  const segments = (view.segments || []).map(cloneSegment);
  const fromFrame = view.frame?.duration_s ?? 0;
  const fromSegments = segments.reduce((max, segment) => Math.max(max, segment.t_end), 0);
  const window = view.analysis_window;
  return {
    version: view.version,
    segments,
    analysis_window: window ? { start_s: window.start_s, end_s: window.end_s } : null,
    duration_s: fromFrame > 0 ? fromFrame : fromSegments,
  };
}

function regionSignature(region: DraftRegion): string {
  return [region.role, round4(region.x), round4(region.y), round4(region.w), round4(region.h)].join(":");
}

export function regionsEquivalent(left: DraftRegion[], right: DraftRegion[]): boolean {
  const a = left.map(regionSignature).sort();
  const b = right.map(regionSignature).sort();
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function windowsEqual(left: DraftWindow, right: DraftWindow): boolean {
  if (!left && !right) return true;
  if (!left || !right) return false;
  return round3(left.start_s) === round3(right.start_s) && round3(left.end_s) === round3(right.end_s);
}

export function draftsEqual(left: LayoutDraft, right: LayoutDraft): boolean {
  if (!windowsEqual(left.analysis_window, right.analysis_window)) return false;
  if (left.segments.length !== right.segments.length) return false;
  for (let index = 0; index < left.segments.length; index += 1) {
    const a = left.segments[index];
    const b = right.segments[index];
    if (round3(a.t_start) !== round3(b.t_start) || round3(a.t_end) !== round3(b.t_end)) return false;
    if (!regionsEquivalent(a.regions, b.regions)) return false;
  }
  return true;
}

export function clampRegion(region: DraftRegion): DraftRegion {
  let w = Math.min(1, Math.max(MIN_REGION, region.w));
  let h = Math.min(1, Math.max(MIN_REGION, region.h));
  let x = Math.min(Math.max(0, region.x), 1 - w);
  let y = Math.min(Math.max(0, region.y), 1 - h);
  if (x + w > 1) w = 1 - x;
  if (y + h > 1) h = 1 - y;
  w = Math.max(MIN_REGION, w);
  h = Math.max(MIN_REGION, h);
  x = Math.min(x, 1 - w);
  y = Math.min(y, 1 - h);
  return { ...region, x: round4(x), y: round4(y), w: round4(w), h: round4(h) };
}

export function nudgeRegion(region: DraftRegion, dxPx: number, dyPx: number, frameW: number, frameH: number): DraftRegion {
  if (frameW <= 0 || frameH <= 0) return region;
  return clampRegion({
    ...region,
    x: region.x + dxPx / frameW,
    y: region.y + dyPx / frameH,
    source: "user",
  });
}

export function moveRegion(region: DraftRegion, dx: number, dy: number): DraftRegion {
  return clampRegion({ ...region, x: region.x + dx, y: region.y + dy, source: "user" });
}

export function resizeRegion(region: DraftRegion, handle: Corner, dx: number, dy: number): DraftRegion {
  let { x, y, w, h } = region;
  if (handle === "ne" || handle === "se") w += dx;
  if (handle === "sw" || handle === "se") h += dy;
  if (handle === "nw" || handle === "sw") {
    x += dx;
    w -= dx;
  }
  if (handle === "nw" || handle === "ne") {
    y += dy;
    h -= dy;
  }
  if (w < MIN_REGION) {
    if (handle === "nw" || handle === "sw") x -= MIN_REGION - w;
    w = MIN_REGION;
  }
  if (h < MIN_REGION) {
    if (handle === "nw" || handle === "ne") y -= MIN_REGION - h;
    h = MIN_REGION;
  }
  return clampRegion({ ...region, x, y, w, h, source: "user" });
}

export function boxFromPoints(a: { x: number; y: number }, b: { x: number; y: number }, role: EditorRole, id: string): DraftRegion | null {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  const w = Math.abs(a.x - b.x);
  const h = Math.abs(a.y - b.y);
  if (w < MIN_REGION || h < MIN_REGION) return null;
  return clampRegion({ id, role, x, y, w, h, source: "user" });
}

function mapSegments(segments: DraftSegment[], segmentIndex: number, regions: (current: DraftRegion[]) => DraftRegion[]): DraftSegment[] {
  return segments.map((segment) => (segment.index === segmentIndex ? { ...segment, regions: regions(segment.regions) } : segment));
}

export function applyRole(segments: DraftSegment[], segmentIndex: number, regionId: string, role: EditorRole): DraftSegment[] {
  return mapSegments(segments, segmentIndex, (regions) =>
    regions.map((region) => {
      if (region.id === regionId) return { ...region, role, source: "user" };
      if ((role === "camera" || role === "screen") && region.role === role) {
        return { ...region, role: "ignore", source: "user" };
      }
      return region;
    }),
  );
}

export function removeRegion(segments: DraftSegment[], segmentIndex: number, regionId: string): DraftSegment[] {
  return mapSegments(segments, segmentIndex, (regions) => regions.filter((region) => region.id !== regionId));
}

export function upsertRegion(segments: DraftSegment[], segmentIndex: number, region: DraftRegion): DraftSegment[] {
  return mapSegments(segments, segmentIndex, (regions) => {
    const index = regions.findIndex((row) => row.id === region.id);
    if (index === -1) {
      if (regions.length >= 8) return regions;
      return [...regions, region];
    }
    const next = regions.slice();
    next[index] = region;
    return next;
  });
}

export function cameraCount(segments: DraftSegment[]): number {
  return segments.reduce((count, segment) => count + segment.regions.filter((region) => region.role === "camera").length, 0);
}

export function isLastCamera(segments: DraftSegment[], regionId: string): boolean {
  const cameras = segments.flatMap((segment) => segment.regions.filter((region) => region.role === "camera"));
  return cameras.length === 1 && cameras[0]?.id === regionId;
}

function reindex(segments: DraftSegment[]): DraftSegment[] {
  return segments.map((segment, index) => ({ ...segment, index }));
}

export function splitSegment(
  segments: DraftSegment[],
  segmentIndex: number,
  at: number,
): { ok: true; segments: DraftSegment[] } | { ok: false; reason: "edge" | "missing" } {
  const current = segments.find((segment) => segment.index === segmentIndex);
  if (!current) return { ok: false, reason: "missing" };
  if (at <= current.t_start + EDGE_SPLIT_S || at >= current.t_end - EDGE_SPLIT_S) return { ok: false, reason: "edge" };
  const right: DraftSegment = {
    ...current,
    index: current.index + 1,
    t_start: at,
    regions: current.regions.map((region) => ({ ...region, id: newRegionId(), source: "user" })),
  };
  const left: DraftSegment = { ...current, t_end: at };
  const next = segments.flatMap((segment) => (segment.index === segmentIndex ? [left, right] : [segment]));
  return { ok: true, segments: reindex(next) };
}

export function proposeMerge(segments: DraftSegment[], segmentIndex: number): "first" | "same" | "differ" | "missing" {
  const ordered = [...segments].sort((a, b) => a.index - b.index);
  const position = ordered.findIndex((segment) => segment.index === segmentIndex);
  if (position < 0) return "missing";
  if (position === 0) return "first";
  return regionsEquivalent(ordered[position - 1].regions, ordered[position].regions) ? "same" : "differ";
}

export function mergeSegments(segments: DraftSegment[], segmentIndex: number, keep: MergeKeep): DraftSegment[] | null {
  const ordered = [...segments].sort((a, b) => a.index - b.index);
  const position = ordered.findIndex((segment) => segment.index === segmentIndex);
  if (position <= 0) return null;
  const left = ordered[position - 1];
  const right = ordered[position];
  const regions = (keep === "left" ? left.regions : right.regions).map((region) => ({ ...region }));
  const merged: DraftSegment = {
    ...left,
    t_end: right.t_end,
    kind: keep === "left" ? left.kind : right.kind,
    confidence: Math.min(left.confidence, right.confidence),
    regions,
  };
  const next = [...ordered.slice(0, position - 1), merged, ...ordered.slice(position + 1)];
  return reindex(next);
}

export type WindowResult =
  | { ok: true; window: DraftWindow }
  | { ok: false; reason: "short" | "disabled" };

export function setWindow(duration: number, start: number, end: number): WindowResult {
  if (duration < MIN_WINDOW_S) return { ok: false, reason: "disabled" };
  const startS = Math.max(0, Math.min(start, duration));
  const endS = Math.max(0, Math.min(end, duration));
  if (endS - startS < MIN_WINDOW_S - 1e-6) return { ok: false, reason: "short" };
  if (startS <= 0.5 && endS >= duration - 0.5) return { ok: true, window: null };
  return { ok: true, window: { start_s: round3(startS), end_s: round3(endS) } };
}

export function activeWindow(draft: LayoutDraft): { start_s: number; end_s: number } {
  if (draft.analysis_window) return draft.analysis_window;
  return { start_s: 0, end_s: draft.duration_s };
}

export function positionWords(region: Pick<DraftRegion, "x" | "y" | "w" | "h">): {
  vertical: "top" | "middle" | "bottom";
  horizontal: "left" | "centre" | "right";
  wPct: number;
  hPct: number;
} {
  const cx = region.x + region.w / 2;
  const cy = region.y + region.h / 2;
  const vertical = cy < 0.33 ? "top" : cy > 0.66 ? "bottom" : "middle";
  const horizontal = cx < 0.33 ? "left" : cx > 0.66 ? "right" : "centre";
  return {
    vertical,
    horizontal,
    wPct: Math.round(region.w * 100),
    hPct: Math.round(region.h * 100),
  };
}

export function roleKey(role: string): "camera" | "screen" | "other" | "ignore" {
  if (role === "camera" || role === "screen" || role === "ignore") return role;
  return "other";
}
