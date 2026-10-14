import type { TranscriptPayload, TranscriptWord } from "./transcript.ts";
import { flattenWords, highlightsFromTranscript } from "./transcript.ts";

export type SeriesPoint = { t: number; value: number | null };
export type SeriesPayload = {
  name: string;
  resolution_s?: number;
  points?: SeriesPoint[];
  unavailable?: boolean;
  na_reason?: string;
};

export const WPM_BANDS: Record<string, [number, number]> = {
  keynote: [130, 165],
  breakout: [130, 165],
  exec_briefing: [125, 160],
  sales_pitch: [130, 165],
  virtual_meeting: [125, 160],
  class_academic: [120, 160],
};

export const FILLER_REF_LOW = 5;
export const FILLER_REF_HIGH = 12;

export type PaceWindow = { t: number; wpm: number | null };

const WORD_RE = /[\wÀ-ÿ'-]+/;

function isLexical(word: TranscriptWord): boolean {
  const text = String(word.word ?? word.w ?? "");
  return WORD_RE.test(text);
}

/** 30-s WPM windows from the transcript. Missing speech is null, never 0. */
export function paceWindows(payload: TranscriptPayload, windowS = 30): PaceWindow[] {
  const words = flattenWords(payload).filter(isLexical);
  const duration = Math.max(
    Number(payload.duration ?? 0),
    ...words.map((word) => Number(word.end ?? 0)),
    windowS,
  );
  const windows: PaceWindow[] = [];
  for (let start = 0; start < duration; start += windowS) {
    const end = start + windowS;
    const count = words.filter((word) => {
      const t = Number(word.start ?? 0);
      return t >= start && t < end;
    }).length;
    windows.push({
      t: start,
      wpm: count === 0 ? null : (count / windowS) * 60,
    });
  }
  return windows;
}

export function availableSeriesPoints(series: SeriesPayload | null | undefined): SeriesPoint[] {
  if (!series || series.unavailable) return [];
  return (series.points ?? []).filter(
    (point) => typeof point.value === "number" && Number.isFinite(point.value),
  );
}

export type PauseBucket = { label: string; count: number; min: number; max: number };

export function pauseHistogram(payload: TranscriptPayload): PauseBucket[] {
  const words = flattenWords(payload);
  const buckets: PauseBucket[] = [
    { label: "0.25–0.5 s", count: 0, min: 0.25, max: 0.5 },
    { label: "0.5–1 s", count: 0, min: 0.5, max: 1 },
    { label: "1–2 s", count: 0, min: 1, max: 2 },
    { label: "2–4 s", count: 0, min: 2, max: 4 },
    { label: "> 4 s", count: 0, min: 4, max: Infinity },
  ];
  for (let i = 0; i < words.length - 1; i += 1) {
    const gap = Number(words[i + 1].start ?? 0) - Number(words[i].end ?? 0);
    if (gap < 0.25) continue;
    const bucket = buckets.find((item) => gap >= item.min && gap < item.max);
    if (bucket) bucket.count += 1;
  }
  return buckets;
}

export type SectionFiller = { id: string; label: string; rate: number | null };

export function fillerRatePerSection(payload: TranscriptPayload): SectionFiller[] {
  const highlights = highlightsFromTranscript(payload).filter((item) => item.kind === "filler_sound");
  return (payload.segments ?? []).map((segment, index) => {
    const start = Number(segment.start ?? 0);
    const end = Number(segment.end ?? start);
    const duration = Math.max(end - start, 0.001);
    const count = highlights.filter((item) => item.start >= start && item.start < end).length;
    const hasSpeech = Boolean(segment.text || segment.words?.length);
    return {
      id: String(segment.id ?? index),
      label: `S${String(index + 1).padStart(2, "0")}`,
      rate: hasSpeech ? (count / duration) * 60 : null,
    };
  });
}

export function wpmBand(contextType: string | undefined): [number, number] {
  return WPM_BANDS[contextType ?? ""] ?? WPM_BANDS.keynote;
}
