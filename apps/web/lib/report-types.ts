/** Analysis-result / report view model from GET /sessions/{id}/report (issue #31). */

export const PILLAR_IDS = [
  "message",
  "story_impact",
  "visuals",
  "voice",
  "body",
  "presence_time",
] as const;

export type PillarId = (typeof PILLAR_IDS)[number];

export const CATEGORY_IDS = [
  "core_message",
  "structure",
  "storytelling",
  "audience_adaptation",
  "opening_close",
  "clarity",
  "impact",
  "visual_aids",
  "pace_pausing",
  "vocal_variety",
  "fluency",
  "gestures_body",
  "eye_contact",
  "facial_affect",
  "energy_presence",
  "time_management",
  "qa",
  "screen_flow",
  "on_camera_presence",
  "online_engagement",
  "production_quality",
] as const;

export type CategoryId = (typeof CATEGORY_IDS)[number];

export type ConfidenceLabel = "high" | "medium" | "low";

export type ReportMetric = {
  id: string;
  category_id: string;
  raw_value: number | string | boolean | null;
  unit: string;
  score: number | null;
  weight: number;
  confidence: number;
  included: boolean;
  basis: { kind: "research" | "heuristic" | "llm_judgment"; source: string };
  target_band?: string | null;
};

export type ReportCategory = {
  id: CategoryId | string;
  pillar: string;
  applicable: boolean;
  na_reason: string | null;
  na_code?: string | null;
  score: number | null;
  level: number | null;
  confidence: number | null;
  confidence_label: ConfidenceLabel | null;
  weight_used: number;
  top_contributors: string[];
  evidence_ids: string[];
  sources: string[];
  counterfactual: string | null;
};

export type ReportPillar = {
  id: PillarId | string;
  score: number | null;
  confidence: number | null;
  categories: string[];
};

export type ReportInsight = {
  category_id: string;
  title: string;
  body: string;
  fix: string | null;
  drill_ids: string[];
  evidence_ids: string[];
  impact_estimate?: number | null;
};

export type ReportEvidence = {
  id: string;
  category_id: string;
  t_start: number;
  t_end: number;
  modality: string;
  kind: string;
  text: string;
  quote?: string | null;
  confidence: number;
  user_disputed?: boolean;
};

export type AnalysisReport = {
  schema_version?: string;
  session?: {
    id: string;
    context_type: string;
    language: string;
    slot_min: number | null;
    qa_in_slot: boolean;
    camera_setup: string;
    talk_plan_id: string | null;
    delivery_mode?: string;
    source_kind?: string;
  };
  core_delivery?: {
    score: number | null;
    confidence?: number | null;
    categories?: string[];
  };
  layout_summary?: {
    kinds?: string[];
    camera_visible_ratio?: number | null;
    screen_visible_ratio?: number | null;
    version?: number;
    status?: string;
  };
  provenance?: {
    scoring_config_version?: string;
    generated_at?: string;
  };
  media?: {
    duration_s: number;
    has_video: boolean;
    has_audio: boolean;
  };
  quality?: {
    warnings?: string[];
  };
  overall: {
    score: number | null;
    level: number | null;
    coverage: number;
    confidence: number;
    display_band: number;
    partial: boolean;
  };
  pillars: ReportPillar[];
  categories: ReportCategory[];
  metrics: ReportMetric[];
  evidence?: ReportEvidence[];
  insights: {
    summary: string;
    strengths: ReportInsight[];
    weaknesses: ReportInsight[];
    opportunities: ReportInsight[];
  };
};

export const KEY_METRIC_IDS = [
  "tm_pct_of_slot",
  "pp_wpm",
  "fl_filler_sounds_per_min",
  "pp_unplanned_long_pauses_per_10min",
  "ec_audience_facing_ratio",
  "vv_pvq_median",
] as const;

export type KeyMetricId = (typeof KEY_METRIC_IDS)[number];
