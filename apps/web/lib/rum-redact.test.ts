import assert from "node:assert/strict";
import { test } from "node:test";
import { redactRumAttributes } from "./rum-redact.ts";

const SESSION = "poison-session-id";
const URL = `https://coach.example.test/sessions/${SESSION}/upload/clip.mp4?email=person@example.test#notes`;

test("session URLs lose the id and the query string", () => {
  const exported = redactRumAttributes({
    "location.href": URL,
    "http.target": `/sessions/${SESSION}?q=poison-query`,
    "error.message": `opened /sessions/${SESSION}`,
    app: "stagecoach",
  });
  const dump = JSON.stringify(exported);
  assert.equal(dump.includes(SESSION), false);
  assert.equal(dump.includes("poison-query"), false);
  assert.equal(dump.includes("?"), false);
  assert.equal(String(exported["location.href"]).startsWith("https://coach.example.test/sessions/redacted/"), true);
  assert.equal(exported.app, "stagecoach");
});

test("prep ids are redacted the same way", () => {
  const exported = redactRumAttributes({
    "location.href": "https://coach.example.test/prep/poison-prep-id",
  });
  assert.equal(exported["location.href"], "https://coach.example.test/prep/redacted");
});
