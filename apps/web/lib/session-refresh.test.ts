import assert from "node:assert/strict";
import { test } from "node:test";
import type { ProgressEvent } from "./progress.ts";
import {
  SESSION_POLL_MS,
  SessionRefresh,
  classifyArtifactStatus,
  etaMinutes,
  ingestStepText,
  retryAfterMs,
  shouldFetchArtifacts,
  type SessionLoadResult,
  type SessionPayload,
} from "./session-refresh.ts";

const LOAD_ERROR = "Could not load this session.";

function flush(): Promise<void> {
  return new Promise((resolve) => setImmediate(resolve));
}

test("retry-after is seconds or an HTTP date", () => {
  assert.equal(retryAfterMs("30", 0), 30_000);
  assert.equal(retryAfterMs("0", 0), 1_000);
  assert.equal(retryAfterMs(new Date(5_000).toUTCString(), 0), 5_000);
  assert.equal(retryAfterMs(null), SESSION_POLL_MS);
});

test("409 is not ready, and artifacts wait for a finished step", () => {
  assert.equal(classifyArtifactStatus(409), "not_ready");
  assert.equal(classifyArtifactStatus(429), "rate_limited");
  assert.equal(classifyArtifactStatus(200), "ok");
  assert.equal(shouldFetchArtifacts("processing", null), false);
  assert.equal(
    shouldFetchArtifacts("processing", { type: "stage", stage: "ingest", status: "running" }),
    false,
  );
  assert.equal(shouldFetchArtifacts("ready", null), true);
  assert.equal(shouldFetchArtifacts("partial", null), true);
  assert.equal(shouldFetchArtifacts("processing", { type: "partial_ready", categories: ["pace_pausing"] }), true);
  assert.equal(shouldFetchArtifacts("processing", { type: "done", status: "ready" }), true);
  assert.equal(
    shouldFetchArtifacts("processing", { type: "stage", stage: "asr", status: "succeeded" }),
    true,
  );
});

test("ingest step codes translate and an eta becomes minutes", () => {
  assert.equal(ingestStepText("ingest_audio", (key) => `tr:${key}`), "tr:prepSteps.audio");
  assert.equal(ingestStepText("Media ready", (key) => `tr:${key}`), "Media ready");
  assert.equal(ingestStepText(null, (key) => key), null);
  assert.equal(etaMinutes(90), 2);
  assert.equal(etaMinutes(0), null);
});

test("a load error clears on the next successful refresh", async () => {
  const errors: Array<string | null> = [];
  const sessions: SessionPayload[] = [];
  let calls = 0;
  const timers: Array<{ fn: () => void; ms: number }> = [];
  const refresh = new SessionRefresh({
    loadError: LOAD_ERROR,
    schedule: (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length;
    },
    cancel: () => undefined,
    loadSession: async () => {
      calls += 1;
      if (calls === 1) return { httpStatus: 500, retryAfter: null, session: null };
      return { httpStatus: 200, retryAfter: null, session: { status: "processing" } };
    },
    loadArtifacts: async () => null,
    onSession: (session) => sessions.push(session),
    onError: (message) => errors.push(message),
  });
  refresh.start();
  await flush();
  assert.deepEqual(errors, [LOAD_ERROR]);
  assert.equal(sessions.length, 0);
  assert.equal(timers.at(-1)?.ms, SESSION_POLL_MS);
  timers.at(-1)?.fn();
  await flush();
  assert.deepEqual(errors, [LOAD_ERROR, null]);
  assert.equal(sessions.at(-1)?.status, "processing");
});

test("429 backs off with retry-after and does not set a load error", async () => {
  const errors: Array<string | null> = [];
  const timers: Array<{ fn: () => void; ms: number }> = [];
  let calls = 0;
  const refresh = new SessionRefresh({
    now: () => 1_000_000,
    loadError: LOAD_ERROR,
    schedule: (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length;
    },
    cancel: () => undefined,
    loadSession: async () => {
      calls += 1;
      if (calls === 1) return { httpStatus: 429, retryAfter: "30", session: null };
      return { httpStatus: 200, retryAfter: null, session: { status: "processing" } };
    },
    loadArtifacts: async () => null,
    onSession: () => undefined,
    onError: (message) => errors.push(message),
  });
  refresh.start();
  await flush();
  assert.deepEqual(errors, []);
  assert.equal(calls, 1);
  assert.equal(timers.at(-1)?.ms, 30_000);
  timers.at(-1)?.fn();
  await flush();
  assert.equal(calls, 2);
  assert.deepEqual(errors, [null]);
});

test("a queued refresh waits out a 429 instead of overlapping", async () => {
  let release: (value: SessionLoadResult) => void = () => undefined;
  let calls = 0;
  const timers: Array<{ fn: () => void; ms: number }> = [];
  const refresh = new SessionRefresh({
    now: () => 1_000_000,
    loadError: LOAD_ERROR,
    schedule: (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length;
    },
    cancel: () => undefined,
    loadSession: () => {
      calls += 1;
      if (calls === 1) return new Promise((resolve) => { release = resolve; });
      return Promise.resolve({ httpStatus: 200, retryAfter: null, session: { status: "processing" } });
    },
    loadArtifacts: async () => null,
    onSession: () => undefined,
    onError: () => undefined,
  });
  refresh.start();
  const done: ProgressEvent = { type: "done", status: "ready" };
  refresh.onEvent(done);
  assert.equal(calls, 1);
  release({ httpStatus: 429, retryAfter: "30", session: null });
  await flush();
  await flush();
  assert.equal(calls, 1);
  assert.equal(timers.at(-1)?.ms, 30_000);
  timers.at(-1)?.fn();
  await flush();
  await flush();
  assert.equal(calls, 2);
});

test("refreshes do not overlap", async () => {
  let release: (value: SessionLoadResult) => void = () => undefined;
  let inFlight = 0;
  let maxInFlight = 0;
  let calls = 0;
  const refresh = new SessionRefresh({
    loadError: LOAD_ERROR,
    schedule: (fn, ms) => setTimeout(fn, ms),
    cancel: (timer) => clearTimeout(timer),
    loadSession: () => {
      calls += 1;
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      if (calls === 1) {
        return new Promise((resolve) => {
          release = (value) => {
            inFlight -= 1;
            resolve(value);
          };
        });
      }
      inFlight -= 1;
      return Promise.resolve({ httpStatus: 200, retryAfter: null, session: { status: "ready" } });
    },
    loadArtifacts: async () => null,
    onSession: () => undefined,
    onError: () => undefined,
  });
  refresh.start();
  refresh.wake();
  refresh.onEvent({ type: "stage", stage: "asr", status: "succeeded" });
  assert.equal(calls, 1);
  assert.equal(maxInFlight, 1);
  release({ httpStatus: 200, retryAfter: null, session: { status: "processing" } });
  await flush();
  await flush();
  assert.equal(maxInFlight, 1);
  assert.ok(calls >= 2);
});
