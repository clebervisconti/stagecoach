/** How the session page refreshes. Progress comes from /events. The poll is a fallback. */

import type { ProgressEvent } from "./progress.ts";

export const SESSION_POLL_MS = 12_000;

const PREP_STEPS = new Set(["check", "poster", "audio", "analysis", "playback", "sprites", "modality"]);

export type SessionPayload = {
  status: string;
  media?: { poster_ready?: boolean; duration_s?: number | null } | null;
};

export type SessionLoadResult = {
  httpStatus: number;
  retryAfter: string | null;
  session: SessionPayload | null;
};

export function retryAfterMs(header: string | null | undefined, now = Date.now()): number {
  if (!header || !header.trim()) return SESSION_POLL_MS;
  const trimmed = header.trim();
  if (/^\d+(\.\d+)?$/.test(trimmed)) return clampDelay(Number(trimmed) * 1000);
  const when = Date.parse(trimmed);
  if (Number.isFinite(when)) return clampDelay(when - now);
  return SESSION_POLL_MS;
}

function clampDelay(ms: number): number {
  if (!Number.isFinite(ms)) return SESSION_POLL_MS;
  return Math.min(120_000, Math.max(1_000, Math.ceil(ms)));
}

export function isTerminalStatus(status: string | null | undefined): boolean {
  return status === "ready" || status === "partial" || status === "failed";
}

/** Artifact reads while a session is still processing are what flooded the API. */
export function shouldFetchArtifacts(status: string | null | undefined, event: ProgressEvent | null): boolean {
  if (status === "ready" || status === "partial") return true;
  if (!event) return false;
  if (event.type === "partial_ready" || event.type === "done") return true;
  return event.type === "stage" && event.status === "succeeded";
}

export function classifyArtifactStatus(status: number): "ok" | "not_ready" | "rate_limited" | "error" {
  if (status === 409) return "not_ready";
  if (status === 429) return "rate_limited";
  if (status >= 200 && status < 300) return "ok";
  return "error";
}

export function ingestStepText(
  message: string | null | undefined,
  translate: (key: string) => string,
): string | null {
  if (!message) return null;
  if (message.startsWith("ingest_")) {
    const code = message.slice("ingest_".length);
    if (PREP_STEPS.has(code)) return translate(`prepSteps.${code}`);
  }
  return message;
}

export function etaMinutes(etaS: number | null | undefined): number | null {
  if (etaS == null || !Number.isFinite(etaS) || etaS <= 0) return null;
  return Math.max(1, Math.round(etaS / 60));
}

type Timer = ReturnType<typeof setTimeout>;

export class SessionRefresh {
  private inFlight = false;
  private queued = false;
  private queuedArtifacts = false;
  private stopped = false;
  private status: string | null = null;
  private timer: Timer | null = null;
  private generation = 0;
  /** After a re-analyse, ignore a stale ready response for a few quick polls. */
  private holdPolls = 0;
  /** Epoch ms. A 429 holds every refresh until this instant, including queued events. */
  private backoffUntil = 0;
  private readonly options: {
    pollMs?: number;
    now?: () => number;
    schedule?: (fn: () => void, ms: number) => Timer;
    cancel?: (timer: Timer) => void;
    loadSession: () => Promise<SessionLoadResult>;
    loadArtifacts: () => Promise<number | null>;
    onSession: (session: SessionPayload) => void;
    onError: (message: string | null) => void;
    loadError: string;
  };

  constructor(options: {
    pollMs?: number;
    now?: () => number;
    schedule?: (fn: () => void, ms: number) => Timer;
    cancel?: (timer: Timer) => void;
    loadSession: () => Promise<SessionLoadResult>;
    loadArtifacts: () => Promise<number | null>;
    onSession: (session: SessionPayload) => void;
    onError: (message: string | null) => void;
    loadError: string;
  }) {
    this.options = options;
  }

  start(): void {
    void this.run(false);
  }

  stop(): void {
    this.stopped = true;
    this.generation += 1;
    this.clearTimer();
  }

  wake(): void {
    this.status = "processing";
    this.holdPolls = 4;
    void this.run(false);
  }

  onEvent(event: ProgressEvent | null): void {
    if (!event || event.type === "connected") return;
    if (event.type === "stage" && event.status === "running") return;
    void this.run(shouldFetchArtifacts(this.status, event));
  }

  private pollMs(): number {
    return this.options.pollMs ?? SESSION_POLL_MS;
  }

  private now(): number {
    return this.options.now?.() ?? Date.now();
  }

  private schedule(fn: () => void, ms: number): Timer {
    const schedule = this.options.schedule ?? ((callback, delay) => setTimeout(callback, delay));
    return schedule(fn, ms);
  }

  private cancel(timer: Timer): void {
    if (this.options.cancel) this.options.cancel(timer);
    else clearTimeout(timer);
  }

  private clearTimer(): void {
    if (this.timer != null) {
      this.cancel(this.timer);
      this.timer = null;
    }
  }

  private arm(ms: number): void {
    if (this.stopped) return;
    this.clearTimer();
    this.timer = this.schedule(() => {
      this.timer = null;
      const artifacts = this.queuedArtifacts;
      this.queued = false;
      this.queuedArtifacts = false;
      this.backoffUntil = 0;
      void this.run(artifacts);
    }, ms);
  }

  private async run(fetchArtifacts: boolean): Promise<void> {
    if (this.stopped) return;
    const wait = this.backoffUntil - this.now();
    if (wait > 0) {
      this.queued = true;
      if (fetchArtifacts) this.queuedArtifacts = true;
      this.arm(wait);
      return;
    }
    if (this.inFlight) {
      this.queued = true;
      if (fetchArtifacts) this.queuedArtifacts = true;
      return;
    }
    this.inFlight = true;
    this.clearTimer();
    const generation = this.generation;
    try {
      const loaded = await this.options.loadSession();
      if (this.stopped || generation !== this.generation) return;
      if (loaded.httpStatus === 429) {
        const delay = retryAfterMs(loaded.retryAfter, this.now());
        this.backoffUntil = this.now() + delay;
        this.arm(delay);
        return;
      }
      if (loaded.httpStatus === 409) {
        if (!isTerminalStatus(this.status)) this.arm(this.pollMs());
        return;
      }
      if (loaded.httpStatus < 200 || loaded.httpStatus >= 300 || !loaded.session) {
        this.options.onError(this.options.loadError);
        if (!isTerminalStatus(this.status)) this.arm(this.pollMs());
        return;
      }
      if (this.holdPolls > 0 && isTerminalStatus(loaded.session.status)) {
        this.holdPolls -= 1;
        this.arm(2_000);
        return;
      }
      this.holdPolls = 0;
      this.status = loaded.session.status;
      this.options.onError(null);
      this.options.onSession(loaded.session);
      const artifacts = fetchArtifacts || shouldFetchArtifacts(this.status, null);
      if (artifacts) {
        const retry = await this.options.loadArtifacts();
        if (this.stopped || generation !== this.generation) return;
        if (retry != null) {
          this.backoffUntil = this.now() + retry;
          this.arm(retry);
          return;
        }
      }
      if (!isTerminalStatus(this.status)) this.arm(this.pollMs());
    } catch {
      if (!this.stopped && generation === this.generation) {
        this.options.onError(this.options.loadError);
        if (!isTerminalStatus(this.status)) this.arm(this.pollMs());
      }
    } finally {
      this.inFlight = false;
      if (this.queued && !this.stopped && generation === this.generation) {
        const again = this.queuedArtifacts;
        this.queued = false;
        this.queuedArtifacts = false;
        void this.run(again);
      }
    }
  }
}
