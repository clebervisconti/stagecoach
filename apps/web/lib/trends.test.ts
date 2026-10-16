import assert from "node:assert/strict";
import test from "node:test";
import { sparklinePath, trendsQuery } from "./trends.ts";

test("trends query includes filters", () => {
  assert.equal(
    trendsQuery({ metric: "pp_wpm", context: "exec_briefing", language: "en" }),
    "/api/stagecoach/trends?metric=pp_wpm&context=exec_briefing&language=en",
  );
  assert.equal(trendsQuery({}), "/api/stagecoach/trends");
});

test("sparkline path has one point per value", () => {
  const path = sparklinePath([1, 2, 3]);
  assert.match(path, /^M/);
  assert.equal(path.split("L").length, 3);
});
