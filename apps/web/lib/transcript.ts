import { formatTimestamp } from "./player.ts";
import { lexiconFor, normalizeToken, type HighlightKind } from "./lexicons.ts";

export type TranscriptWord = {
  word?: string;
  w?: string;
  start?: number;
  end?: number;
  probability?: number;
  p?: number;
  tags?: string[];
};

export type TranscriptSegment = {
  id?: string | number;
  start?: number;
  end?: number;
  speaker?: string | null;
  text?: string;
  words?: TranscriptWord[];
};

export type FluencyDisambiguation = {
  hit_id?: string;
  word?: string;
  token?: string;
  t_start?: number;
  t_end?: number;
  context_before?: string;
  context_after?: string;
  is_filler?: boolean;
  confidence?: number;
  method?: string;
};

export type TranscriptPayload = {
  language?: string | null;
  duration?: number;
  segments?: TranscriptSegment[];
  words?: TranscriptWord[];
  highlights?: Array<{
    kind?: string;
    category_id?: string;
    metric_id?: string;
    t_start?: number;
    t_end?: number;
    text?: string;
    quote?: string | null;
  }>;
  disambiguations?: FluencyDisambiguation[];
};

export type WordHighlight = {
  start: number;
  end: number;
  text: string;
  kind: HighlightKind;
  confirmed: boolean;
};

const LONG_PAUSE_S = 1.0;

function wordText(word: TranscriptWord): string {
  return String(word.word ?? word.w ?? "").trim();
}

export function flattenWords(payload: TranscriptPayload): TranscriptWord[] {
  if (payload.words?.length) return payload.words;
  const words: TranscriptWord[] = [];
  for (const segment of payload.segments ?? []) {
    if (segment.words?.length) {
      words.push(...segment.words);
      continue;
    }
    const tokens = String(segment.text ?? "").split(/\s+/).filter(Boolean);
    const start = Number(segment.start ?? 0);
    const end = Number(segment.end ?? start);
    const step = (end - start) / Math.max(tokens.length, 1);
    tokens.forEach((token, index) => {
      words.push({
        word: token,
        start: start + index * step,
        end: start + (index + 1) * step,
      });
    });
  }
  return words;
}

function tagsOf(word: TranscriptWord): string[] {
  return (word.tags ?? []).map((tag) => tag.toLowerCase());
}

export function classifyWord(
  word: TranscriptWord,
  language: string | null | undefined,
  confirmedKinds: Set<HighlightKind>,
): WordHighlight[] {
  const text = wordText(word);
  if (!text) return [];
  const start = Number(word.start ?? 0);
  const end = Number(word.end ?? start);
  const token = normalizeToken(text);
  const lexicon = lexiconFor(language);
  const tags = tagsOf(word);
  const hits: WordHighlight[] = [];

  const add = (kind: HighlightKind, confirmed: boolean) => {
    hits.push({ start, end, text, kind, confirmed });
  };

  if (tags.includes("filler_sound") || lexicon.filler_sounds.includes(token as never)) {
    add("filler_sound", true);
  } else if (tags.includes("filler_word") || lexicon.filler_words.includes(token as never)) {
    add("filler_word", tags.includes("filler_word") || confirmedKinds.has("filler_word"));
  }
  if (tags.includes("hedge") || lexicon.hedges.includes(token as never)) {
    add("hedge", tags.includes("hedge"));
  }
  if (tags.includes("vague") || lexicon.vague.includes(token as never)) {
    add("vague", tags.includes("vague"));
  }
  return hits;
}

export function highlightsFromTranscript(payload: TranscriptPayload): WordHighlight[] {
  const words = flattenWords(payload);
  const confirmed = new Set<HighlightKind>();
  for (const item of payload.highlights ?? []) {
    if (item.metric_id === "fl_filler_sounds_per_min" || item.kind === "filler_sound") {
      confirmed.add("filler_sound");
    }
    if (item.category_id === "core_message") confirmed.add("core_message");
    if (item.category_id === "impact") confirmed.add("clt");
  }
  const out: WordHighlight[] = [];
  words.forEach((word, index) => {
    out.push(...classifyWord(word, payload.language, confirmed));
    const next = words[index + 1];
    const gap = Number(next?.start ?? 0) - Number(word.end ?? 0);
    if (next && gap >= LONG_PAUSE_S) {
      out.push({
        start: Number(word.end ?? 0),
        end: Number(next.start ?? 0),
        text: `⏸ ${gap.toFixed(1)} s`,
        kind: "pause",
        confirmed: true,
      });
    }
  });
  for (const item of payload.highlights ?? []) {
    const start = Number(item.t_start ?? 0);
    const end = Number(item.t_end ?? start);
    if (item.category_id === "core_message") {
      out.push({
        start,
        end,
        text: item.quote || item.text || "",
        kind: "core_message",
        confirmed: true,
      });
    }
    if (item.category_id === "impact") {
      out.push({
        start,
        end,
        text: item.quote || item.text || "",
        kind: "clt",
        confirmed: true,
      });
    }
  }
  return out;
}

export function fillerBreakdown(highlights: WordHighlight[]): Array<{ token: string; count: number }> {
  const counts = new Map<string, number>();
  for (const item of highlights) {
    if (item.kind !== "filler_sound" && item.kind !== "filler_word") continue;
    const token = normalizeToken(item.text);
    counts.set(token, (counts.get(token) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([token, count]) => ({ token, count }))
    .sort((a, b) => b.count - a.count || a.token.localeCompare(b.token));
}

export function exportTxt(payload: TranscriptPayload): string {
  return (payload.segments ?? [])
    .map((segment) => {
      const speaker = segment.speaker ? `${segment.speaker}: ` : "";
      const time = formatTimestamp(Number(segment.start ?? 0));
      return `[${time}] ${speaker}${segment.text ?? ""}`.trim();
    })
    .join("\n");
}

function srtTime(seconds: number): string {
  const ms = Math.max(0, Math.round(seconds * 1000));
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  const secs = Math.floor((ms % 60_000) / 1000);
  const milli = ms % 1000;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")},${String(milli).padStart(3, "0")}`;
}

export function exportSrt(payload: TranscriptPayload): string {
  return (payload.segments ?? [])
    .map((segment, index) => {
      const start = Number(segment.start ?? 0);
      const end = Number(segment.end ?? start + 1);
      return `${index + 1}\n${srtTime(start)} --> ${srtTime(end)}\n${segment.text ?? ""}\n`;
    })
    .join("\n");
}

export function exportVtt(payload: TranscriptPayload): string {
  const body = (payload.segments ?? [])
    .map((segment) => {
      const start = Number(segment.start ?? 0);
      const end = Number(segment.end ?? start + 1);
      return `${srtTime(start).replace(",", ".")} --> ${srtTime(end).replace(",", ".")}\n${segment.text ?? ""}`;
    })
    .join("\n\n");
  return `WEBVTT\n\n${body}\n`;
}
