/** SSE progress events (SPEC §7.6, issue #46). */

export type StageProgressEvent = {
  type: "stage";
  stage: string;
  status: string;
  pct?: number | null;
  message?: string | null;
  session_id?: string | null;
  job_id?: string | null;
};

export type PartialReadyEvent = {
  type: "partial_ready";
  categories: string[];
  session_id?: string | null;
  job_id?: string | null;
};

export type DoneProgressEvent = {
  type: "done";
  status: string;
  session_id?: string | null;
  job_id?: string | null;
};

export type ConnectedProgressEvent = {
  type: "connected";
  job_id?: string | null;
};

export type ProgressEvent =
  | StageProgressEvent
  | PartialReadyEvent
  | DoneProgressEvent
  | ConnectedProgressEvent;

export function parseProgressData(raw: string): ProgressEvent | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const type = row.type;
  if (type === "partial_ready") {
    const categories = Array.isArray(row.categories)
      ? row.categories.filter((item): item is string => typeof item === "string")
      : [];
    return { type: "partial_ready", categories };
  }
  if (type === "done") {
    return { type: "done", status: typeof row.status === "string" ? row.status : "ready" };
  }
  if (type === "connected") {
    return { type: "connected", job_id: typeof row.job_id === "string" ? row.job_id : null };
  }
  if (type === "stage" || typeof row.stage === "string") {
    return {
      type: "stage",
      stage: typeof row.stage === "string" ? row.stage : "pipeline",
      status: typeof row.status === "string" ? row.status : "running",
      pct: typeof row.pct === "number" ? row.pct : null,
      message: typeof row.message === "string" ? row.message : null,
    };
  }
  return null;
}

export function shouldReloadReport(event: ProgressEvent | null): boolean {
  return event?.type === "partial_ready" || event?.type === "done";
}

export function eventsUrl(sessionId: string): string {
  return `/api/stagecoach/sessions/${sessionId}/events`;
}

import { pipelineStages as stagesForMode } from "./online.ts";

export const PIPELINE_STAGES = [
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

export function pipelineStages(deliveryMode = "stage", sourceKind = "upload"): readonly string[] {
  return stagesForMode(deliveryMode, sourceKind);
}

export type StageState = "pending" | "running" | "succeeded" | "failed" | "skipped" | "waiting";

export type StepSnapshot = {
  stage: string;
  status: string;
  message?: string | null;
  error?: string | null;
  detail?: string | null;
  problem?: string | null;
};

export type StageView = {
  stage: string;
  status: StageState;
  detail: string | null;
  problem: "visionUnavailable" | "consent_video_off" | null;
};

function asStageState(status: string): StageState {
  if (
    status === "pending" ||
    status === "running" ||
    status === "succeeded" ||
    status === "failed" ||
    status === "skipped" ||
    status === "waiting"
  ) {
    return status;
  }
  if (status === "unavailable") return "skipped";
  return "running";
}

export function stageProblem(error: string | null | undefined): "visionUnavailable" | "consent_video_off" | null {
  if (!error) return null;
  if (/consent_video_off/i.test(error)) return "consent_video_off";
  if (/mediapipe|modulenotfounderror/i.test(error)) return "visionUnavailable";
  return null;
}

const PREPARE_STAGES = new Set(["ingest", "layout", "layout_review", "sync", "region_crops"]);
const PAST_REVIEW = new Set(["processing", "ready", "partial", "failed"]);
const TERMINAL = new Set(["ready", "partial", "failed"]);

export function pipelineTimeline(
  steps: StepSnapshot[],
  live?: StageProgressEvent | null,
  options?: {
    deliveryMode?: string;
    sourceKind?: string;
    sessionStatus?: string;
    layoutConfirmed?: "user" | "auto" | null;
  },
): StageView[] {
  const deliveryMode = options?.deliveryMode ?? "stage";
  const foldAlignment = deliveryMode !== "stage";
  const byStage = new Map<string, StepSnapshot>();
  for (const step of steps) byStage.set(step.stage, step);
  if (live?.type === "stage") {
    const previous = byStage.get(live.stage);
    byStage.set(live.stage, {
      stage: live.stage,
      status: live.status,
      message: live.message ?? previous?.message ?? null,
      error: previous?.error ?? null,
    });
  }
  if (foldAlignment) {
    const alignment = byStage.get("alignment");
    if (alignment && (alignment.status === "running" || alignment.status === "pending" || alignment.status === "waiting")) {
      const asr = byStage.get("asr");
      byStage.set("asr", {
        stage: "asr",
        status: "running",
        message: asr?.message ?? alignment.message ?? null,
        error: asr?.error ?? null,
      });
    }
    byStage.delete("alignment");
  }

  const names = [...pipelineStages(deliveryMode, options?.sourceKind ?? "upload")] as string[];
  for (const step of byStage.values()) {
    if (foldAlignment && step.stage === "alignment") continue;
    if (!names.includes(step.stage)) names.push(step.stage);
  }
  if (live?.type === "stage" && !(foldAlignment && live.stage === "alignment") && !names.includes(live.stage)) {
    names.push(live.stage);
  }

  const rows = names.map((stage) => {
    const step = byStage.get(stage);
    if (!step) return { stage, status: "pending" as StageState, detail: null, problem: null };
    const status = asStageState(step.status);
    const problem =
      status === "failed" || status === "skipped"
        ? (step.problem === "consent_video_off" ? "consent_video_off" : null) ||
          stageProblem(step.problem) ||
          stageProblem(step.error) ||
          stageProblem(step.message)
        : null;
    const raw = status === "failed" ? step.error || step.message : step.message;
    return {
      stage,
      status,
      detail: problem ? null : raw?.trim() || null,
      problem,
    };
  });

  if (foldAlignment) {
    const review = rows.find((row) => row.stage === "layout_review");
    const laterDone = rows.some(
      (row) => !PREPARE_STAGES.has(row.stage) && (row.status === "succeeded" || row.status === "running"),
    );
    const pastReview = PAST_REVIEW.has(options?.sessionStatus ?? "");
    if (
      review &&
      review.status !== "skipped" &&
      (pastReview || laterDone) &&
      (review.status === "pending" || review.status === "waiting")
    ) {
      review.status = "succeeded";
      review.detail =
        options?.layoutConfirmed === "auto" ? "confirmed_automatically" : "by_you";
    }
    const busy = rows.some((row) => row.status === "running" || row.status === "waiting");
    if (!busy && !TERMINAL.has(options?.sessionStatus ?? "")) {
      const firstPending = rows.find((row) => row.status === "pending");
      if (firstPending) firstPending.status = "running";
    }
  }

  return rows;
}
