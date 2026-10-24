import {
  KEY_METRIC_IDS,
  PILLAR_IDS,
  type AnalysisReport,
  type KeyMetricId,
  type ReportCategory,
  type ReportMetric,
  type ReportPillar,
} from "./report-types.ts";

export const LEVEL_NAME_KEYS = {
  1: "level1",
  2: "level2",
  3: "level3",
  4: "level4",
  5: "level5",
} as const;

export type SlotLight = "green" | "yellow" | "red" | null;

export type KeyMetricRow = {
  id: KeyMetricId;
  available: boolean;
  raw_value: number | null;
  formatted: string | null;
  unit: string | null;
  score: number | null;
  confidence: number | null;
  basisKind: "research" | "heuristic" | "llm_judgment" | null;
  source: string | null;
  light: SlotLight;
};

export type RadarPoint = {
  id: string;
  score: number | null;
  available: boolean;
  confidence: number | null;
  categories: string[];
};

/** Pillars with no applicable scored categories stay unavailable. Never coerce null to 0. */
export function radarPoints(report: AnalysisReport): RadarPoint[] {
  const byId = new Map(report.pillars.map((pillar) => [pillar.id, pillar]));
  return PILLAR_IDS.map((id) => {
    const pillar: ReportPillar | undefined = byId.get(id);
    const score = pillar?.score ?? null;
    const available = typeof score === "number" && Number.isFinite(score);
    return {
      id,
      score: available ? score : null,
      available,
      confidence: pillar?.confidence ?? null,
      categories: pillar?.categories ?? [],
    };
  });
}

export function overallHeadline(report: AnalysisReport): {
  score: number | null;
  band: number;
  level: number | null;
  levelKey: (typeof LEVEL_NAME_KEYS)[keyof typeof LEVEL_NAME_KEYS] | null;
  partial: boolean;
  coverage: number;
  confidence: number;
} {
  const overall = report.overall;
  const level =
    typeof overall.level === "number" && overall.level >= 1 && overall.level <= 5
      ? (overall.level as 1 | 2 | 3 | 4 | 5)
      : null;
  return {
    score: overall.score,
    band: overall.display_band ?? 0,
    level,
    levelKey: level ? LEVEL_NAME_KEYS[level] : null,
    partial: Boolean(overall.partial) || overall.coverage < 0.6,
    coverage: overall.coverage,
    confidence: overall.confidence,
  };
}

export function formatOverallLine(
  score: number | null,
  band: number,
  levelName: string | null,
): string {
  if (score === null) return "—";
  const core = `${score} ± ${band}`;
  return levelName ? `${core} · ${levelName}` : core;
}

/** A partial report names itself partial. The level word stays for a full score. */
export function overallLevelWord(
  partial: boolean,
  levelName: string | null,
  partialLabel: string,
): string | null {
  if (partial) return partialLabel;
  return levelName;
}

const SESSION_WIDE_METRICS = new Set([
  "pp_wpm",
  "pp_articulation_rate_sps",
  "pp_pace_cv",
  "pp_rush_index",
  "pp_mean_length_of_run",
  "fl_filler_sounds_per_min",
  "fl_filler_words_per_min",
  "fl_hedges_apologies_per_10min",
  "fl_repetitions_restarts_per_min",
  "pq_integrated_lufs",
  "pq_clipping_ratio",
  "pq_snr_db",
  "pq_true_peak_dbtp",
  "pq_frozen_video_s",
]);

export function isSessionWideEvidence(item: {
  t_start: number;
  quote?: string | null;
  text?: string;
  metric_id?: string | null;
  span?: string | null;
}): boolean {
  if (item.span === "session") return true;
  if (item.metric_id && SESSION_WIDE_METRICS.has(item.metric_id)) return true;
  if ((item.quote || "").trim()) return false;
  if (item.t_start > 0.05) return false;
  const text = (item.text || "").toLowerCase();
  return (
    text.includes("words per minute") ||
    text.includes("speaking rate") ||
    text.includes("filler-sound") ||
    text.includes("filler sound") ||
    text.includes("palavras por minuto")
  );
}

function asNumber(value: ReportMetric["raw_value"]): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Toastmasters-style slot traffic light. Heuristic, not a research curve. */
export function slotTrafficLight(ratio: number | null): SlotLight {
  if (ratio === null) return null;
  if (ratio >= 0.9 && ratio <= 1.0) return "green";
  if ((ratio >= 0.8 && ratio < 0.9) || (ratio > 1.0 && ratio <= 1.15)) return "yellow";
  return "red";
}

export function formatKeyMetricValue(id: KeyMetricId, raw: number): string {
  if (id === "tm_pct_of_slot" || id === "ec_audience_facing_ratio") {
    return `${Math.round(raw * 100)}%`;
  }
  if (id === "pp_wpm") {
    return String(Math.round(raw));
  }
  if (Number.isInteger(raw)) return String(raw);
  return raw.toFixed(2).replace(/\.?0+$/, "");
}

export function keyMetricRows(report: AnalysisReport): KeyMetricRow[] {
  const byId = new Map(report.metrics.map((metric) => [metric.id, metric]));
  return KEY_METRIC_IDS.map((id) => {
    const metric = byId.get(id);
    const raw = metric ? asNumber(metric.raw_value) : null;
    const available = raw !== null;
    return {
      id,
      available,
      raw_value: raw,
      formatted: available ? formatKeyMetricValue(id, raw) : null,
      unit: metric?.unit ?? null,
      score: available ? (metric?.score ?? null) : null,
      confidence: metric?.confidence ?? null,
      basisKind: metric?.basis.kind ?? null,
      source: metric?.basis.source ?? null,
      light: id === "tm_pct_of_slot" ? slotTrafficLight(raw) : null,
    };
  });
}

export function categoriesByPillar(report: AnalysisReport): Map<string, ReportCategory[]> {
  const grouped = new Map<string, ReportCategory[]>();
  for (const id of PILLAR_IDS) grouped.set(id, []);
  for (const category of report.categories) {
    const pillar = PILLAR_IDS.includes(category.pillar as (typeof PILLAR_IDS)[number])
      ? category.pillar
      : "message";
    const list = grouped.get(pillar) ?? [];
    list.push(category);
    grouped.set(pillar, list);
  }
  for (const [pillar, list] of grouped) {
    list.sort((a, b) => {
      const aScore = a.applicable && a.score !== null ? a.score : -1;
      const bScore = b.applicable && b.score !== null ? b.score : -1;
      return aScore - bScore;
    });
    grouped.set(pillar, list);
  }
  return grouped;
}

export function metricsById(report: AnalysisReport): Map<string, ReportMetric> {
  return new Map(report.metrics.map((metric) => [metric.id, metric]));
}

export function evidenceById(report: AnalysisReport): Map<string, NonNullable<AnalysisReport["evidence"]>[number]> {
  return new Map((report.evidence ?? []).map((item) => [item.id, item]));
}

export function unavailableCategoryLabel(category: ReportCategory): string {
  if (category.applicable && category.score !== null) return "";
  return category.na_reason || "unavailable";
}

/** Radar vertices for available pillars only. N/A axes are omitted (a gap), never plotted at 0. */
export function radarPolygon(points: RadarPoint[], radius: number, cx: number, cy: number): string {
  const vertices: string[] = [];
  points.forEach((point, index) => {
    if (!point.available || point.score === null) return;
    const angle = (-Math.PI / 2) + (index * 2 * Math.PI) / points.length;
    const r = (point.score / 100) * radius;
    vertices.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`);
  });
  return vertices.join(" ");
}

export const CATEGORY_PILLAR: Record<string, string> = {
  core_message: "message",
  structure: "message",
  opening_close: "message",
  clarity: "message",
  storytelling: "story_impact",
  audience_adaptation: "story_impact",
  impact: "story_impact",
  visual_aids: "visuals",
  pace_pausing: "voice",
  vocal_variety: "voice",
  fluency: "voice",
  gestures_body: "body",
  eye_contact: "body",
  facial_affect: "body",
  energy_presence: "presence_time",
  time_management: "presence_time",
  qa: "presence_time",
  screen_flow: "visuals",
  on_camera_presence: "body",
  online_engagement: "presence_time",
  production_quality: "production",
};

export type GoalLike = {
  category_id?: string | null;
  metric_id?: string | null;
  target: number;
};

/** Dashed goal ring: category targets are 0–100 scores mapped onto pillars. */
export function goalRadarPoints(base: RadarPoint[], goals: GoalLike[]): RadarPoint[] {
  const byPillar = new Map<string, number>();
  for (const goal of goals) {
    const pillar = goal.category_id ? CATEGORY_PILLAR[goal.category_id] : undefined;
    if (!pillar) continue;
    const current = byPillar.get(pillar) ?? 0;
    byPillar.set(pillar, Math.max(current, goal.target));
  }
  return base.map((point) => {
    const score = byPillar.get(point.id);
    return {
      ...point,
      score: score ?? null,
      available: score != null,
      confidence: score != null ? 1 : null,
    };
  });
}

export function radarAxisPoint(
  index: number,
  count: number,
  radius: number,
  cx: number,
  cy: number,
): { x: number; y: number } {
  const angle = (-Math.PI / 2) + (index * 2 * Math.PI) / count;
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
}
