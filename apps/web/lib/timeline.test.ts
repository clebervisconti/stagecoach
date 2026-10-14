import assert from "node:assert/strict";
import { test } from "node:test";
import {
  TIMELINE_LANE_IDS,
  defaultEnabledLanes,
  laneMarkers,
  playheadPercent,
  spriteUrl,
  timeFromClick,
  type TimelinePayload,
} from "./timeline.ts";

const payload: TimelinePayload = {
  duration_s: 100,
  sprite_interval_s: 5,
  lanes: [
    {
      id: "fillers",
      available: true,
      default_on: true,
      items: [
        { t_start: 4, t_end: 4.4, label: "um", kind: "filler" },
        { t_start: 20, t_end: 20.3, label: "uh", kind: "filler" },
      ],
    },
    { id: "smiles", available: true, opt_in: true, default_on: false, items: [] },
    { id: "qa", available: false, items: [] },
  ],
};

test("spec lane ids stay in §8.4 order", () => {
  assert.deepEqual(TIMELINE_LANE_IDS, [
    "sections",
    "slides",
    "fillers",
    "long_pauses",
    "rushing",
    "monotone",
    "gestures",
    "audience_facing",
    "smiles",
    "clt_story",
    "qa",
  ]);
});

test("click seeks and playhead stays within the duration", () => {
  assert.equal(timeFromClick(50, { left: 0, width: 100 }, 40), 20);
  assert.equal(playheadPercent(10, 40), 25);
  assert.equal(playheadPercent(80, 40), 100);
  assert.equal(spriteUrl("abc", 12), "/api/stagecoach/sessions/abc/sprite?t=12");
});

test("smiles stay off by default even when available", () => {
  const enabled = defaultEnabledLanes(payload);
  assert.equal(enabled.has("fillers"), true);
  assert.equal(enabled.has("smiles"), false);
  assert.equal(enabled.has("qa"), false);
  assert.equal(laneMarkers(payload.lanes[0])[1]?.t, 20);
});
