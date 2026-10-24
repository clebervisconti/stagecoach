/** Browser half of the chunked recording upload. See ADR-085.

Each request stays at or below the server's chunk size (8 MiB), under
Cloudflare's 100 MB proxied-body cap. A dropped chunk is retried. A later
attempt sends only the chunks the server does not already have.
*/

import { MAX_UPLOAD_BYTES } from "./online.ts";
import { classifyUploadFailure, safeUploadDetail } from "./upload-errors.ts";

export const DEFAULT_CHUNK_BYTES = 8 * 1024 * 1024;
export const MAX_CHUNK_BYTES = 32 * 1024 * 1024;
const ATTEMPTS = 4;

export type UploadTelemetry = {
  loaded: number;
  total: number;
  pct: number;
  speed: number;
  eta: number | null;
};

export type UploadRequest = {
  url: string;
  method: "GET" | "POST" | "PUT";
  body?: Blob | string | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  onProgress?: (loaded: number, total: number) => void;
};

export type UploadResponse = {
  status: number;
  text: string;
};

export type UploadTransport = (request: UploadRequest) => Promise<UploadResponse>;

export type ChunkUploadOutcome =
  | { ok: true; status: number; uploadId: string }
  | { ok: false; status: number; code: string | null; detail: string; uploadId: string | null };

type ParsedBody = {
  code: string | null;
  detail: string;
  payload: Record<string, unknown>;
};

type Sleeper = (ms: number, signal?: AbortSignal) => Promise<void>;

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function abortError(): Error {
  const error = new Error("upload cancelled");
  error.name = "AbortError";
  return error;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(abortError());
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function backoffMs(attempt: number): number {
  if (attempt <= 0) return 250;
  if (attempt === 1) return 750;
  return 2000;
}

export function safeFilename(name: string): string {
  const base = name.split(/[/\\]/).pop() || "recording.mp4";
  if (base.length <= 200) return base;
  const dot = base.lastIndexOf(".");
  const extension = dot > 0 ? base.slice(dot, dot + 16) : "";
  return `${base.slice(0, Math.max(1, 200 - extension.length))}${extension}`;
}

function parsePayload(text: string): ParsedBody {
  try {
    const payload = JSON.parse(text) as unknown;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return { code: null, detail: safeUploadDetail(text, ""), payload: {} };
    }
    const record = payload as Record<string, unknown>;
    const code = typeof record.code === "string" ? record.code : null;
    const nested = record.detail;
    let detail = "";
    if (typeof nested === "string") detail = nested;
    else if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      const inner = (nested as Record<string, unknown>).detail;
      if (typeof inner === "string") detail = inner;
    }
    return { code, detail, payload: record };
  } catch {
    return { code: null, detail: safeUploadDetail(text, ""), payload: {} };
  }
}

function readChunkBytes(payload: Record<string, unknown>): number | null {
  const value = payload.chunk_bytes;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1 || value > MAX_CHUNK_BYTES) {
    return null;
  }
  return value;
}

function readUploadId(payload: Record<string, unknown>): string | null {
  const value = payload.upload_id;
  return typeof value === "string" && /^[a-f0-9]{32}$/.test(value) ? value : null;
}

function chunkCount(size: number, chunkBytes: number): number {
  return Math.ceil(size / chunkBytes);
}

function chunkLength(index: number, chunkBytes: number, size: number): number {
  const start = index * chunkBytes;
  return Math.max(0, Math.min(chunkBytes, size - start));
}

function missingIndexes(payload: Record<string, unknown>, count: number): number[] {
  const raw = payload.missing;
  if (!Array.isArray(raw)) return Array.from({ length: count }, (_, index) => index);
  const found = new Set<number>();
  for (const value of raw) {
    if (typeof value === "number" && Number.isInteger(value) && value >= 0 && value < count) found.add(value);
  }
  return [...found].sort((left, right) => left - right);
}

function xhrTransport(request: UploadRequest): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(request.method, request.url);
    for (const [key, value] of Object.entries(request.headers ?? {})) xhr.setRequestHeader(key, value);
    if (request.onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) request.onProgress?.(event.loaded, event.total);
      };
    }
    const onAbort = () => xhr.abort();
    request.signal?.addEventListener("abort", onAbort, { once: true });
    xhr.onerror = () => {
      request.signal?.removeEventListener("abort", onAbort);
      resolve({ status: 0, text: "" });
    };
    xhr.onabort = () => {
      request.signal?.removeEventListener("abort", onAbort);
      reject(abortError());
    };
    xhr.onload = () => {
      request.signal?.removeEventListener("abort", onAbort);
      resolve({ status: xhr.status, text: xhr.responseText || "" });
    };
    if (request.signal?.aborted) {
      reject(abortError());
      return;
    }
    xhr.send(request.body ?? null);
  });
}

async function fetchTransport(request: UploadRequest): Promise<UploadResponse> {
  try {
    const response = await fetch(request.url, {
      method: request.method,
      headers: request.headers,
      body: request.body ?? undefined,
      signal: request.signal,
    });
    const text = await response.text();
    if (request.onProgress && request.body instanceof Blob) {
      request.onProgress(request.body.size, request.body.size);
    }
    return { status: response.status, text };
  } catch (error) {
    if (isAbortError(error)) throw error;
    return { status: 0, text: "" };
  }
}

export function browserTransport(request: UploadRequest): Promise<UploadResponse> {
  if (typeof XMLHttpRequest === "undefined") return fetchTransport(request);
  return xhrTransport(request);
}

async function call(
  transport: UploadTransport,
  request: UploadRequest,
  fileSize: number,
  maxBytes: number,
  sleeper: Sleeper,
): Promise<{ status: number; code: string | null; detail: string; payload: Record<string, unknown> }> {
  let last = { status: 0, code: null as string | null, detail: "", payload: {} as Record<string, unknown> };
  for (let attempt = 0; attempt < ATTEMPTS; attempt += 1) {
    if (request.signal?.aborted) throw abortError();
    let response: UploadResponse;
    try {
      response = await transport(request);
    } catch (error) {
      if (isAbortError(error)) throw error;
      response = { status: 0, text: "" };
    }
    const parsed = parsePayload(response.text);
    last = { status: response.status, code: parsed.code, detail: parsed.detail, payload: parsed.payload };
    if (response.status >= 200 && response.status < 300) return last;
    if (response.status === 413) return last;
    if (
      parsed.code === "file_too_large" ||
      parsed.code === "chunk_conflict" ||
      parsed.code === "unsupported_type" ||
      parsed.code === "incomplete" ||
      parsed.code === "bad_chunk"
    ) {
      return last;
    }
    const classified = classifyUploadFailure({
      fileSize,
      maxBytes,
      status: response.status,
      code: parsed.code,
    });
    if (!classified.retry || attempt === ATTEMPTS - 1) return last;
    await sleeper(backoffMs(attempt), request.signal);
  }
  return last;
}

export async function uploadRecordingChunked(options: {
  sessionId: string;
  file: Blob & { name?: string; type?: string };
  rightsAttested?: boolean;
  uploadId?: string | null;
  apiPrefix?: string;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  maxBytes?: number;
  transport?: UploadTransport;
  sleeper?: Sleeper;
  onUploadId?: (uploadId: string) => void;
  onProgress?: (value: UploadTelemetry) => void;
}): Promise<ChunkUploadOutcome> {
  const fileSize = options.file.size;
  const maxBytes = options.maxBytes ?? MAX_UPLOAD_BYTES;
  const transport = options.transport ?? browserTransport;
  const sleeper = options.sleeper ?? sleep;
  const prefix = (options.apiPrefix ?? "/api/stagecoach").replace(/\/$/, "");
  const headers = options.headers ?? {};
  const started = Date.now();
  let uploadId = options.uploadId ?? null;

  const report = (loaded: number) => {
    const elapsed = Math.max(0.2, (Date.now() - started) / 1000);
    const speed = loaded / elapsed;
    const remaining = Math.max(0, fileSize - loaded);
    options.onProgress?.({
      loaded,
      total: fileSize,
      pct: fileSize > 0 ? Math.min(100, Math.round((loaded / fileSize) * 100)) : 0,
      speed,
      eta: speed > 0 ? remaining / speed : null,
    });
  };

  const fail = (
    status: number,
    code: string | null,
    detail: string,
  ): ChunkUploadOutcome => ({ ok: false, status, code, detail, uploadId });

  if (fileSize > maxBytes) return fail(413, "file_too_large", "");
  if (fileSize < 1) return fail(400, "empty", "Uploaded file is empty");

  const endpoint = (suffix: string) => `${prefix}/sessions/${options.sessionId}/uploads${suffix}`;

  let chunkBytes = DEFAULT_CHUNK_BYTES;
  let missing: number[] | null = null;

  if (uploadId) {
    const status = await call(
      transport,
      { url: endpoint(`/${uploadId}`), method: "GET", headers, signal: options.signal },
      fileSize,
      maxBytes,
      sleeper,
    );
    if (status.status >= 200 && status.status < 300) {
      if (status.payload.already === true) {
        report(fileSize);
        return { ok: true, status: status.status, uploadId };
      }
      const declared = readChunkBytes(status.payload);
      if (!declared) return fail(500, "bad_config", "Chunk size is not proxy-safe");
      chunkBytes = declared;
      missing = missingIndexes(status.payload, chunkCount(fileSize, chunkBytes));
    } else if (status.status !== 404) {
      return fail(status.status, status.code, status.detail);
    } else {
      uploadId = null;
    }
  }

  if (!uploadId) {
    const created = await call(
      transport,
      {
        url: endpoint(""),
        method: "POST",
        headers: { ...headers, "content-type": "application/json" },
        body: JSON.stringify({
          filename: safeFilename(options.file.name || "recording.mp4"),
          content_type: (options.file.type || "application/octet-stream").slice(0, 127),
          size: fileSize,
          rights_attested: Boolean(options.rightsAttested),
        }),
        signal: options.signal,
      },
      fileSize,
      maxBytes,
      sleeper,
    );
    if (created.status < 200 || created.status >= 300) return fail(created.status, created.code, created.detail);
    const createdId = readUploadId(created.payload);
    const declared = readChunkBytes(created.payload);
    if (!createdId || !declared) return fail(500, "bad_config", "Upload was not opened");
    uploadId = createdId;
    chunkBytes = declared;
    missing = missingIndexes(created.payload, chunkCount(fileSize, chunkBytes));
    options.onUploadId?.(uploadId);
  }

  const count = chunkCount(fileSize, chunkBytes);
  const pending = missing ?? Array.from({ length: count }, (_, index) => index);
  let loaded = 0;
  for (let index = 0; index < count; index += 1) {
    if (!pending.includes(index)) loaded += chunkLength(index, chunkBytes, fileSize);
  }
  report(loaded);

  for (const index of pending) {
    const start = index * chunkBytes;
    const blob = options.file.slice(start, Math.min(fileSize, start + chunkBytes));
    if (blob.size > MAX_CHUNK_BYTES) return fail(413, "chunk_too_large", "Chunk is larger than the proxy allows");
    const base = loaded;
    const stored = await call(
      transport,
      {
        url: endpoint(`/${uploadId}/chunks/${index}`),
        method: "PUT",
        headers: { ...headers, "content-type": "application/octet-stream" },
        body: blob,
        signal: options.signal,
        onProgress: (sent) => report(base + sent),
      },
      fileSize,
      maxBytes,
      sleeper,
    );
    if (stored.status < 200 || stored.status >= 300) return fail(stored.status, stored.code, stored.detail);
    loaded += blob.size;
    report(loaded);
  }

  let done = await call(
    transport,
    {
      url: endpoint(`/${uploadId}/complete`),
      method: "POST",
      headers,
      signal: options.signal,
    },
    fileSize,
    maxBytes,
    sleeper,
  );
  if (done.code === "incomplete") {
    const again = await call(
      transport,
      { url: endpoint(`/${uploadId}`), method: "GET", headers, signal: options.signal },
      fileSize,
      maxBytes,
      sleeper,
    );
    if (again.status < 200 || again.status >= 300) return fail(again.status, again.code, again.detail);
    for (const index of missingIndexes(again.payload, count)) {
      const start = index * chunkBytes;
      const blob = options.file.slice(start, Math.min(fileSize, start + chunkBytes));
      const stored = await call(
        transport,
        {
          url: endpoint(`/${uploadId}/chunks/${index}`),
          method: "PUT",
          headers: { ...headers, "content-type": "application/octet-stream" },
          body: blob,
          signal: options.signal,
        },
        fileSize,
        maxBytes,
        sleeper,
      );
      if (stored.status < 200 || stored.status >= 300) return fail(stored.status, stored.code, stored.detail);
    }
    done = await call(
      transport,
      { url: endpoint(`/${uploadId}/complete`), method: "POST", headers, signal: options.signal },
      fileSize,
      maxBytes,
      sleeper,
    );
  }
  if (done.status < 200 || done.status >= 300) return fail(done.status, done.code, done.detail);
  report(fileSize);
  return { ok: true, status: done.status, uploadId };
}
