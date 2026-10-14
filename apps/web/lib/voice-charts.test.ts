import assert from "node:assert/strict";
import { test } from "node:test";
import {
  availableSeriesPoints,
  fillerRatePerSection,
  paceWindows,
  pauseHistogram,
} from "./voice-charts.ts";

const transcript = {
  language: "en",
  duration: 60,
  segments: [
    {
      id: 0,
      start: 0,
      end: 30,
      text: "Um hello there friends",
      words: [
        { word: "Um", start: 0, end: 0.3, tags: ["filler_sound"] },
        { word: "hello", start: 0.4, end: 0.8 },
        { word: "there", start: 5.0, end: 5.3 },
        { word: "friends", start: 5.4, end: 6.0 },
      ],
    },
    { id: 1, start: 30, end: 60, text: "", words: [] },
  ],
};

test("pace windows use null when a window has no speech", () => {
  const windows = paceWindows(transcript, 30);
  assert.equal(windows[0]?.wpm !== null, true);
  assert.equal(windows[1]?.wpm, null);
});

test("unavailable series are not treated as zeros", () => {
  const empty = availableSeriesPoints({
    name: "pitch",
    unavailable: true,
    points: [
      { t: 0, value: 0 },
      { t: 1, value: 0 },
    ],
  });
  assert.deepEqual(empty, []);
  const sparse = availableSeriesPoints({
    name: "pitch",
    points: [
      { t: 0, value: null },
      { t: 1, value: 3.2 },
    ],
  });
  assert.equal(sparse.length, 1);
  assert.equal(sparse[0]?.value, 3.2);
});

test("pause histogram and filler-per-section use transcript evidence only", () => {
  const pauses = pauseHistogram(transcript);
  assert.ok(pauses.some((bucket) => bucket.count > 0));
  const rates = fillerRatePerSection(transcript);
  assert.ok((rates[0]?.rate ?? 0) > 0);
  assert.equal(rates[1]?.rate, null);
});
