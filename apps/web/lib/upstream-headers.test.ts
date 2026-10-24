import assert from "node:assert/strict";
import { test } from "node:test";
import { upstreamResponseHeaders } from "./upstream-headers.ts";

test("a 429 keeps retry-after and drops anything else", () => {
  const headers = upstreamResponseHeaders(
    new Headers({
      "content-type": "application/problem+json",
      "retry-after": "30",
      "x-request-id": "secret",
    }),
  );
  assert.equal(headers.get("retry-after"), "30");
  assert.equal(headers.get("content-type"), "application/problem+json");
  assert.equal(headers.get("cache-control"), "no-store");
  assert.equal(headers.get("x-request-id"), null);
});

test("an event stream stays unbuffered", () => {
  const headers = upstreamResponseHeaders(new Headers({ "content-type": "text/event-stream" }));
  assert.equal(headers.get("cache-control"), "no-cache");
  assert.equal(headers.get("x-accel-buffering"), "no");
});
