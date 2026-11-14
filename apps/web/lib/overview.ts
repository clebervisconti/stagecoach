export type ScorePoint = {
  at: string;
  overall: number;
};

export function greetingPart(hour: number): "morning" | "afternoon" | "evening" {
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}

export function numericScores<T extends { overall: number | null; created_at: string }>(sessions: T[]): ScorePoint[] {
  return sessions
    .filter((session): session is T & { overall: number } => typeof session.overall === "number" && Number.isFinite(session.overall))
    .map((session) => ({ at: session.created_at, overall: session.overall }))
    .sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
}

export function averageLast(points: ScorePoint[], count = 3): number | null {
  if (!points.length) return null;
  const slice = points.slice(-count);
  const total = slice.reduce((sum, point) => sum + point.overall, 0);
  return Math.round(total / slice.length);
}

/** Sentence about measured overall scores. Never includes a title, email, or path. */
export function overallFinding(points: ScorePoint[]): string | null {
  if (points.length < 2) return null;
  const first = Math.round(points[0].overall);
  const last = Math.round(points[points.length - 1].overall);
  const count = points.length;
  if (last > first) return `Overall rose from ${first} to ${last} across ${count} sessions`;
  if (last < first) return `Overall fell from ${first} to ${last} across ${count} sessions`;
  return `Overall held at ${last} across ${count} sessions`;
}

export function metricNumber(metrics: { id: string; raw_value: number | string | boolean | null }[] | undefined, id: string): number | null {
  const raw = metrics?.find((metric) => metric.id === id)?.raw_value;
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}
