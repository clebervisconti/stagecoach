import assert from "node:assert/strict";
import { test } from "node:test";
import {
  evidenceSeekTime,
  formatTimestamp,
  nextMarker,
  playbackProxyUrl,
  playerCommand,
  previousMarker,
  seekError,
} from "./player.ts";

test("evidence chips seek to t_start minus 2 seconds", () => {
  assert.equal(evidenceSeekTime(12.4), 10.4);
  assert.equal(evidenceSeekTime(1.2), 0);
  assert.equal(evidenceSeekTime(0), 0);
  assert.ok(seekError(10.4, 12.4) <= 0.5);
  assert.ok(seekError(0, 1.2) <= 0.5);
});

test("keyboard map covers space, arrows, and J/L markers", () => {
  assert.equal(playerCommand({ key: " " }), "toggle");
  assert.equal(playerCommand({ key: "ArrowLeft" }), "back");
  assert.equal(playerCommand({ key: "ArrowRight" }), "forward");
  assert.equal(playerCommand({ key: "j" }), "prevMarker");
  assert.equal(playerCommand({ key: "L" }), "nextMarker");
  assert.equal(playerCommand({ key: "x" }), null);
});

test("marker walk is ordered by time", () => {
  const markers = [
    { id: "a", t: 4 },
    { id: "b", t: 20 },
    { id: "c", t: 11 },
  ];
  assert.equal(nextMarker(markers, 5)?.id, "c");
  assert.equal(previousMarker(markers, 12)?.id, "c");
  assert.equal(formatTimestamp(72), "01:12");
});

test("signed playback URL is rewritten through the BFF", () => {
  const url = playbackProxyUrl("abc", {
    url: "http://api:8000/api/v1/sessions/abc/media?exp=9&sig=deadbeef",
  });
  assert.equal(url, "/api/stagecoach/sessions/abc/media?exp=9&sig=deadbeef");
});
