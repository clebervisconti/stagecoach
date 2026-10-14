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
