/** PDF export helpers (SPEC §8.9, issue #49). */

export const PDF_SECTIONS = [
  "cover",
  "opportunities",
  "strengths",
  "categories",
  "time",
  "metrics",
  "drills",
  "methodology",
] as const;

export type PdfExportStatus = {
  id: string;
  status: "queued" | "running" | "ready" | "failed" | string;
  include_transcript?: boolean;
  download?: string | null;
  error?: string | null;
};

export function exportUrl(sessionId: string): string {
  return `/api/stagecoach/sessions/${sessionId}/export/pdf`;
}

export function exportStatusUrl(exportId: string): string {
  return `/api/stagecoach/exports/${exportId}`;
}

export function exportFileUrl(exportId: string): string {
  return `/api/stagecoach/exports/${exportId}/file`;
}

export function printPath(sessionId: string, includeTranscript: boolean): string {
  const q = includeTranscript ? "?includeTranscript=1" : "";
  return `/sessions/${sessionId}/print${q}`;
}
