/** Map an upload failure to the sentence the wizard should show.

"File too large" is only for a recording over the product limit. A 413 from
Cloudflare, or from a chunk the proxy refused, is a proxy failure and can
be retried. See ADR-085.
*/

export const PRODUCT_MAX_BYTES = 2 * 1024 * 1024 * 1024;

export type UploadFailureKind = "too_large" | "proxy" | "network" | "other";

export type ClassifiedUploadFailure = {
  kind: UploadFailureKind;
  retry: boolean;
};

export function classifyUploadFailure(input: {
  fileSize: number;
  maxBytes: number;
  status: number;
  code?: string | null;
}): ClassifiedUploadFailure {
  if (input.fileSize > input.maxBytes) {
    return { kind: "too_large", retry: false };
  }
  if (input.code === "incomplete") {
    return { kind: "network", retry: true };
  }
  if (
    input.status === 413 ||
    input.code === "chunk_too_large" ||
    input.code === "proxy_rejected" ||
    input.code === "file_too_large"
  ) {
    return { kind: "proxy", retry: true };
  }
  if (input.status === 0 || input.status === 408 || input.status === 429 || input.status >= 500) {
    return { kind: "network", retry: true };
  }
  return { kind: "other", retry: false };
}

export function safeUploadDetail(detail: string | null | undefined, fallback: string): string {
  const text = (detail || "").replace(/\s+/g, " ").trim();
  if (!text || text.startsWith("<") || text.length > 240) return fallback;
  return text;
}

export function uploadErrorCopy(input: {
  fileSize: number;
  maxBytes: number;
  status: number;
  code?: string | null;
  detail?: string | null;
  tooLarge: (size: number) => string;
  proxy: () => string;
  network: () => string;
  other: (detail: string) => string;
}): { kind: UploadFailureKind; message: string; retry: boolean } {
  const classified = classifyUploadFailure(input);
  if (classified.kind === "too_large") {
    return { ...classified, message: input.tooLarge(input.fileSize) };
  }
  if (classified.kind === "proxy") {
    return { ...classified, message: input.proxy() };
  }
  if (classified.kind === "network") {
    return { ...classified, message: input.network() };
  }
  return { ...classified, message: input.other(safeUploadDetail(input.detail, "")) };
}
