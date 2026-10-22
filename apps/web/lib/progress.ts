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

export type StageState = "pending" | "running" | "succeeded" | "failed" | "skipped";

export type StepSnapshot = {
  stage: string;
  status: string;
  message?: string | null;
  error?: string | null;
};

export type StageView = {
  stage: string;
  status: StageState;
  detail: string | null;
  problem: "visionUnavailable" | null;
};

function asStageState(status: string): StageState {
  if (
    status === "pending" ||
    status === "running" ||
    status === "succeeded" ||
    status === "failed" ||
    status === "skipped"
  ) {
    return status;
  }
  if (status === "unavailable") return "skipped";
  return "running";
}

export function stageProblem(error: string | null | undefined): "visionUnavailable" | null {
  if (!error) return null;
  if (/mediapipe|modulenotfounderror/i.test(error)) return "visionUnavailable";
  return null;
}

export function pipelineTimeline(
  steps: StepSnapshot[],
  live?: StageProgressEvent | null,
  options?: { deliveryMode?: string; sourceKind?: string },
): StageView[] {
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

  const names = [...pipelineStages(options?.deliveryMode ?? "stage", options?.sourceKind ?? "upload")] as string[];
  for (const step of steps) {
    if (!names.includes(step.stage)) names.push(step.stage);
  }
  if (live?.type === "stage" && !names.includes(live.stage)) names.push(live.stage);

  return names.map((stage) => {
    const step = byStage.get(stage);
    if (!step) return { stage, status: "pending", detail: null, problem: null };
    const status = asStageState(step.status);
    const problem =
      status === "failed" || status === "skipped"
        ? stageProblem(step.error) || stageProblem(step.message)
        : null;
    const raw = status === "failed" ? step.error || step.message : step.message;
    return {
      stage,
      status,
      detail: problem ? null : raw?.trim() || null,
      problem,
    };
  });
}
