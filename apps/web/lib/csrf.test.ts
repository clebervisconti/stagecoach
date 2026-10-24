import assert from "node:assert/strict";
import { test } from "node:test";
import { mutationAllowed } from "./csrf.ts";

test("GET is allowed without an Origin", () => {
  assert.equal(
    mutationAllowed({
      method: "GET",
      origin: null,
      host: "stagecoach.example",
      forwardedHost: null,
      secFetchSite: null,
    }),
    true,
  );
});

test("same-origin mutations are allowed", () => {
  assert.equal(
    mutationAllowed({
      method: "POST",
      origin: "https://stagecoach.example",
      host: "stagecoach.example",
      forwardedHost: null,
      secFetchSite: "same-origin",
    }),
    true,
  );
});

test("a forwarded host may differ from the internal host", () => {
  assert.equal(
    mutationAllowed({
      method: "DELETE",
      origin: "https://stagecoach.example",
      host: "web:3000",
      forwardedHost: "stagecoach.example",
      secFetchSite: "same-origin",
    }),
    true,
  );
});

test("cross-site mutations are rejected", () => {
  assert.equal(
    mutationAllowed({
      method: "POST",
      origin: "https://stagecoach.example",
      host: "stagecoach.example",
      forwardedHost: null,
      secFetchSite: "cross-site",
    }),
    false,
  );
});

test("a mutation without Origin is rejected", () => {
  assert.equal(
    mutationAllowed({
      method: "PATCH",
      origin: null,
      host: "stagecoach.example",
      forwardedHost: null,
      secFetchSite: null,
    }),
    false,
  );
});

test("a foreign Origin is rejected", () => {
  assert.equal(
    mutationAllowed({
      method: "POST",
      origin: "https://evil.example",
      host: "stagecoach.example",
      forwardedHost: "stagecoach.example",
      secFetchSite: "same-origin",
    }),
    false,
  );
});
