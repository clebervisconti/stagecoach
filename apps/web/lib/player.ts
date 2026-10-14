/** Player seeking and keyboard helpers (SPEC §8.4). */

export const EVIDENCE_PREROLL_S = 2;
export const SKIP_S = 5;

/** Seek to t_start − 2 s, never before 0. Exact float; UI/tests allow ±0.5 s. */
export function evidenceSeekTime(tStart: number): number {
  if (!Number.isFinite(tStart) || tStart < 0) return 0;
  return Math.max(0, tStart - EVIDENCE_PREROLL_S);
}

export function seekError(actual: number, tStart: number): number {
  return Math.abs(actual - evidenceSeekTime(tStart));
}

export function formatTimestamp(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

export type Marker = { id: string; t: number };

export function nextMarker(markers: Marker[], current: number): Marker | null {
  const upcoming = markers
    .filter((marker) => marker.t > current + 0.05)
    .sort((a, b) => a.t - b.t);
  return upcoming[0] ?? null;
}

export function previousMarker(markers: Marker[], current: number): Marker | null {
  const earlier = markers
    .filter((marker) => marker.t < current - 0.05)
    .sort((a, b) => b.t - a.t);
  return earlier[0] ?? null;
}

export type PlayerCommand = "toggle" | "back" | "forward" | "prevMarker" | "nextMarker";

export function playerCommand(event: { key: string; code?: string }): PlayerCommand | null {
  if (event.key === " " || event.code === "Space") return "toggle";
  if (event.key === "ArrowLeft") return "back";
  if (event.key === "ArrowRight") return "forward";
  if (event.key === "j" || event.key === "J") return "prevMarker";
  if (event.key === "l" || event.key === "L") return "nextMarker";
  return null;
}

export function playbackProxyUrl(
  sessionId: string,
  playback: { url?: string } | null,
): string {
  const fallback = `/api/stagecoach/sessions/${sessionId}/media`;
  if (!playback?.url) return fallback;
  try {
    const parsed = new URL(playback.url, "http://localhost");
    const exp = parsed.searchParams.get("exp");
    const sig = parsed.searchParams.get("sig");
    if (exp && sig) {
      return `${fallback}?exp=${encodeURIComponent(exp)}&sig=${encodeURIComponent(sig)}`;
    }
  } catch {
    return fallback;
  }
  return fallback;
}
