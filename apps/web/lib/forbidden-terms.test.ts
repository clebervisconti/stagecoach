import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { collectStrings, findForbiddenEmotionTerm } from "./forbidden-terms.ts";

const here = dirname(fileURLToPath(import.meta.url));

test("en and pt-BR UI strings do not use emotion-inference terms", () => {
  for (const locale of ["en", "pt-BR"]) {
    const messages = JSON.parse(readFileSync(join(here, "..", "messages", `${locale}.json`), "utf8"));
    for (const text of collectStrings(messages)) {
      const hit = findForbiddenEmotionTerm(text);
      assert.equal(hit, null, `${locale} UI string uses forbidden term ${hit}: ${text}`);
    }
  }
});

test("consent policy strings do not use emotion-inference terms", () => {
  const policy = JSON.parse(
    readFileSync(join(here, "../../../packages/consent/v1.json"), "utf8"),
  );
  for (const text of collectStrings(policy)) {
    const hit = findForbiddenEmotionTerm(text);
    assert.equal(hit, null, `consent policy uses forbidden term ${hit}: ${text}`);
  }
});
