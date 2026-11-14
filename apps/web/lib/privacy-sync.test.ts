import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

test("the published privacy notice matches the repository document", () => {
  const published = readFileSync(new URL("../content/PRIVACY.md", import.meta.url), "utf8");
  const source = readFileSync(new URL("../../../docs/PRIVACY.md", import.meta.url), "utf8");
  assert.equal(published, source);
  assert.equal(/@[a-z0-9.-]+\.[a-z]{2,}/i.test(published), false);
  assert.equal(published.includes("/Users/"), false);
  assert.equal(published.includes("Splunk"), true);
});
