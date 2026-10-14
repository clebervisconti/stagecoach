import assert from "node:assert/strict";
import { test } from "node:test";
import {
  exportSrt,
  exportTxt,
  exportVtt,
  fillerBreakdown,
  highlightsFromTranscript,
} from "./transcript.ts";

const payload = {
  language: "en",
  duration: 8,
  segments: [
    {
      id: "S0001",
      start: 0,
      end: 4,
      speaker: "SPK_0",
      text: "Um hello everyone",
      words: [
        { word: "Um", start: 0, end: 0.4, tags: ["filler_sound"] },
        { word: "hello", start: 0.5, end: 0.9 },
        { word: "everyone", start: 3.2, end: 3.8 },
      ],
    },
  ],
  highlights: [
    {
      category_id: "core_message",
      t_start: 0.5,
      t_end: 3.8,
      quote: "hello everyone",
    },
  ],
};

test("transcript highlights fillers, pauses, and API core-message spans", () => {
  const highlights = highlightsFromTranscript(payload);
  assert.ok(highlights.some((item) => item.kind === "filler_sound" && item.text === "Um"));
  assert.ok(highlights.some((item) => item.kind === "pause"));
  assert.ok(highlights.some((item) => item.kind === "core_message"));
  assert.equal(
    highlights.some((item) => item.kind === "clt"),
    false,
    "CLT highlights are not invented without impact evidence",
  );
});

test("filler breakdown counts um", () => {
  const counts = fillerBreakdown(highlightsFromTranscript(payload));
  assert.equal(counts[0]?.token, "um");
  assert.equal(counts[0]?.count, 1);
});

test("exports txt, srt, and vtt from existing segments", () => {
  assert.match(exportTxt(payload), /\[00:00\] SPK_0: Um hello everyone/);
  assert.match(exportSrt(payload), /00:00:00,000 --> 00:00:04,000/);
  assert.match(exportVtt(payload), /^WEBVTT/);
});
