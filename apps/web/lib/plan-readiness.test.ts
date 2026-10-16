import assert from "node:assert/strict";
import test from "node:test";
import { readinessRows, topChanges } from "./plan-readiness.ts";

test("categories 9–15 are N/A until rehearsal", () => {
  const rows = readinessRows({ description: "A 20-minute exec briefing" });
  const delivery = rows.filter((row) =>
    ["pace_pausing", "fluency", "eye_contact"].includes(row.id),
  );
  assert.ok(delivery.length >= 3);
  assert.ok(delivery.every((row) => row.applicable === false && row.na_reason));
  const materials = rows.find((row) => row.id === "core_message");
  assert.equal(materials?.applicable, true);
  assert.equal(materials?.ready, true);
});

test("top 3 changes prefer missing message, structure, and budget", () => {
  const changes = topChanges({});
  assert.equal(changes.length, 3);
  assert.equal(changes[0]?.id, "core_message");
  assert.ok(changes[0]?.rewrite);
});
