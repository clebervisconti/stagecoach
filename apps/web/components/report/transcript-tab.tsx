"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { formatTimestamp } from "@/lib/player";
import type { HighlightKind } from "@/lib/lexicons";
import {
  exportSrt,
  exportTxt,
  exportVtt,
  fillerBreakdown,
  highlightsFromTranscript,
  type TranscriptPayload,
  type TranscriptSegment,
} from "@/lib/transcript";

const TOGGLES: HighlightKind[] = [
  "filler_sound",
  "filler_word",
  "hedge",
  "vague",
  "clt",
  "core_message",
  "pause",
];

const KIND_CLASS: Record<HighlightKind, string> = {
  filler_sound: "bg-red-200 text-red-950",
  filler_word: "bg-amber-200 text-amber-950",
  hedge: "bg-purple-200 text-purple-950",
  vague: "underline decoration-dotted decoration-muted-foreground",
  clt: "bg-emerald-200 text-emerald-950",
  core_message: "bg-sky-200 font-semibold text-sky-950",
  pause: "text-muted-foreground",
};

type TranscriptTabProps = {
  payload: TranscriptPayload | null;
  onSeek: (tStart: number) => void;
};

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function wordKind(
  start: number,
  enabled: Set<HighlightKind>,
  highlights: ReturnType<typeof highlightsFromTranscript>,
): HighlightKind | null {
  const hit = highlights.find(
    (item) => item.kind !== "pause" && enabled.has(item.kind) && start >= item.start && start < item.end,
  );
  return hit?.kind ?? null;
}

export function TranscriptTab({ payload, onSeek }: TranscriptTabProps) {
  const t = useTranslations("report");
  const [enabled, setEnabled] = useState<Set<HighlightKind>>(
    () => new Set<HighlightKind>(["filler_sound", "filler_word", "pause", "core_message"]),
  );
  const highlights = useMemo(() => (payload ? highlightsFromTranscript(payload) : []), [payload]);
  const breakdown = useMemo(() => fillerBreakdown(highlights), [highlights]);
  const segments = payload?.segments ?? [];

  function toggle(kind: HighlightKind) {
    setEnabled((current) => {
      const next = new Set(current);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
      <div>
        <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label={t("highlightToggles")}>
          {TOGGLES.map((kind) => (
            <button
              key={kind}
              type="button"
              aria-pressed={enabled.has(kind)}
              onClick={() => toggle(kind)}
              className={`rounded-full border px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                enabled.has(kind) ? KIND_CLASS[kind] : "bg-muted text-muted-foreground"
              }`}
            >
              {t(`highlights.${kind}`)}
            </button>
          ))}
        </div>
        <div className="max-h-[32rem] space-y-3 overflow-y-auto pr-2">
          {segments.map((segment: TranscriptSegment, index) => (
            <div key={String(segment.id ?? index)} className="rounded-md p-2">
              <p className="mb-1 font-mono text-xs text-muted-foreground">
                {segment.speaker || t("speakerUnknown")} · {formatTimestamp(Number(segment.start ?? 0))}
              </p>
              <p className="leading-7">
                {(segment.words?.length
                  ? segment.words
                  : String(segment.text ?? "")
                      .split(/\s+/)
                      .filter(Boolean)
                      .map((token, wordIndex) => ({
                        word: token,
                        start: Number(segment.start ?? 0) + wordIndex * 0.01,
                      }))
                ).map((word, wordIndex) => {
                  const start = Number(word.start ?? 0);
                  const kind = wordKind(start, enabled, highlights);
                  return (
                    <button
                      key={`${start}-${wordIndex}`}
                      type="button"
                      onClick={() => onSeek(start)}
                      className={`mr-1 rounded-sm px-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        kind ? KIND_CLASS[kind] : "hover:bg-muted"
                      }`}
                    >
                      {word.word}
                    </button>
                  );
                })}
                {enabled.has("pause") &&
                  highlights
                    .filter(
                      (item) =>
                        item.kind === "pause" &&
                        item.start >= Number(segment.start ?? 0) &&
                        item.start < Number(segment.end ?? Infinity),
                    )
                    .map((item) => (
                      <span key={`p-${item.start}`} className="ml-1 text-xs text-muted-foreground">
                        {item.text}
                      </span>
                    ))}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => payload && download("transcript.txt", exportTxt(payload))}
          >
            {t("exportTxt")}
          </button>
          <button
            type="button"
            className="rounded-md border px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => payload && download("transcript.srt", exportSrt(payload))}
          >
            {t("exportSrt")}
          </button>
          <button
            type="button"
            className="rounded-md border px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => payload && download("transcript.vtt", exportVtt(payload))}
          >
            {t("exportVtt")}
          </button>
        </div>
      </div>
      <aside className="rounded-lg border bg-muted/40 p-4 text-sm">
        <h3 className="font-medium">{t("fillerBreakdown")}</h3>
        {breakdown.length ? (
          <ul className="mt-3 space-y-1">
            {breakdown.map((item) => (
              <li key={item.token}>
                {item.token} ×{item.count}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-muted-foreground">{t("noFillers")}</p>
        )}
      </aside>
    </div>
  );
}
