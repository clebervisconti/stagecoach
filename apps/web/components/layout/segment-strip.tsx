"use client";

import { useTranslations } from "next-intl";
import { formatClock, formatRange, layoutComposition, type LayoutSegment } from "@/lib/online";

export function SegmentStrip({
  segments,
  selected,
  onSelect,
}: {
  segments: LayoutSegment[];
  selected: number;
  onSelect: (index: number) => void;
}) {
  const t = useTranslations("online");
  const duration = segments[0]?.t_end ?? 0;
  return (
    <div className="mt-6">
      <div className="flex items-center justify-between gap-3">
        <p className="cs-eyebrow">{t("layoutOverTime")}</p>
        <p className="font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
          {t("segmentCount", { n: String(segments.length) })}
        </p>
      </div>
      <div role="listbox" aria-label={t("layoutOverTime")} className="mt-3 flex gap-2 overflow-x-auto">
        {segments.map((segment) => {
          const composition = layoutComposition(segment);
          const summary =
            composition === "camera_screen"
              ? t("composition.cameraScreen")
              : composition === "camera"
                ? t("composition.camera")
                : composition === "screen"
                  ? t("composition.screen")
                  : t("composition.none");
          const selectedChip = selected === segment.index;
          return (
            <button
              key={segment.index}
              type="button"
              role="option"
              aria-selected={selectedChip}
              aria-label={t("segmentAria", {
                n: String(segment.index + 1),
                of: String(segments.length),
                start: formatClock(segment.t_start),
                end: formatClock(segment.t_end),
                summary,
              })}
              onClick={() => onSelect(segment.index)}
              className={`shrink-0 rounded-full px-3 py-1 font-mono text-xs uppercase tracking-[0.08em] ${
                selectedChip
                  ? "bg-[color:var(--bg-inverse)] text-[color:var(--text-inverse)]"
                  : "border border-[color:var(--line-strong)]"
              }`}
            >
              {formatRange(segment.t_start, segment.t_end)} · {summary}
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex justify-between font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
        <span>{formatClock(0)}</span>
        <span className="hidden md:inline">{formatClock(duration / 2)}</span>
        <span>{formatClock(duration)}</span>
      </div>
    </div>
  );
}
