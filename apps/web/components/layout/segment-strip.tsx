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
  const duration = segments[0]?.t_end ?? 0;
  return (
    <div className="mt-6">
      <div className="flex items-center justify-between gap-3">
        <p className="cs-eyebrow">Layout over time</p>
        <p className="font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
          {segments.length} segment{segments.length === 1 ? "" : "s"}
        </p>
      </div>
      <div role="listbox" aria-label="Layout segments" className="mt-3 flex gap-2 overflow-x-auto">
        {segments.map((segment) => {
          const composition = layoutComposition(segment);
          const summary =
            composition === "camera_screen"
              ? "Camera + screen"
              : composition === "camera"
                ? "Camera only"
                : composition === "screen"
                  ? "Screen only"
                  : "No video";
          const selectedChip = selected === segment.index;
          return (
            <button
              key={segment.index}
              type="button"
              role="option"
              aria-selected={selectedChip}
              aria-label={`Segment ${segment.index + 1} of ${segments.length}, ${formatClock(segment.t_start)} to ${formatClock(segment.t_end)}, ${summary}`}
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
