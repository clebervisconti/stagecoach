"use client";

import { useRef, type PointerEvent as ReactPointerEvent } from "react";
import { useTranslations } from "next-intl";
import { formatClock, formatRange, layoutComposition, type LayoutSegment } from "@/lib/online";
import { activeWindow, MIN_WINDOW_S, type LayoutDraft } from "@/lib/layout-edit";

export function SegmentEditor({
  draft,
  selected,
  playhead,
  message,
  onSelect,
  onPlayhead,
  onSplit,
  onMerge,
  onAdd,
  onWindow,
}: {
  draft: LayoutDraft;
  selected: number;
  playhead: number;
  message: string | null;
  onSelect: (index: number) => void;
  onPlayhead: (time: number) => void;
  onSplit: () => void;
  onMerge: () => void;
  onAdd: () => void;
  onWindow: (start: number, end: number) => void;
}) {
  const t = useTranslations("online");
  const trackRef = useRef<HTMLDivElement>(null);
  const duration = Math.max(draft.duration_s, 0);
  const windowSpan = activeWindow(draft);
  const trimEnabled = duration >= MIN_WINDOW_S;
  const selectedSegment = draft.segments.find((segment) => segment.index === selected) ?? draft.segments[0];
  const splitOk = Boolean(
    selectedSegment && playhead > selectedSegment.t_start + 1 && playhead < selectedSegment.t_end - 1,
  );

  function timeAt(clientX: number): number {
    const track = trackRef.current?.getBoundingClientRect();
    if (!track || track.width <= 0) return 0;
    const ratio = Math.min(1, Math.max(0, (clientX - track.left) / track.width));
    return ratio * duration;
  }

  function dragHandle(which: "start" | "end", event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    const pointerId = event.pointerId;
    event.currentTarget.setPointerCapture(pointerId);
    const move = (next: PointerEvent) => {
      const time = timeAt(next.clientX);
      if (which === "start") onWindow(Math.min(time, windowSpan.end_s - MIN_WINDOW_S), windowSpan.end_s);
      else onWindow(windowSpan.start_s, Math.max(time, windowSpan.start_s + MIN_WINDOW_S));
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }

  return (
    <div className="mt-6 min-w-0" data-testid="segment-editor">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
        <p className="cs-eyebrow">{t("layoutOverTime")}</p>
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
            {t("segmentCount", { n: draft.segments.length })}
          </p>
          <button type="button" data-testid="split-segment" disabled={!splitOk} onClick={onSplit} className="h-9 border border-[color:var(--line-strong)] px-3 text-xs uppercase tracking-[0.08em] disabled:opacity-40">
            {t("layout.cta.split")}
          </button>
          <button
            type="button"
            data-testid="merge-segment"
            disabled={selected <= 0}
            onClick={onMerge}
            className="h-9 border border-[color:var(--line-strong)] px-3 text-xs uppercase tracking-[0.08em] disabled:opacity-40"
          >
            {t("layout.cta.merge")}
          </button>
          <button type="button" data-testid="add-segment" disabled={!splitOk} onClick={onAdd} className="h-9 border border-[color:var(--line-strong)] px-3 text-xs uppercase tracking-[0.08em] disabled:opacity-40">
            {t("layout.cta.add")}
          </button>
        </div>
      </div>
      <div role="listbox" aria-label={t("layoutOverTime")} className="cs-segment-row mt-3 flex w-full min-w-0 gap-2 overflow-x-auto">
        {draft.segments.map((segment) => {
          const view = segment as LayoutSegment;
          const composition = layoutComposition(view);
          const summary =
            composition === "camera_screen"
              ? t("composition.cameraScreen")
              : composition === "camera"
                ? t("composition.camera")
                : composition === "screen"
                  ? t("composition.screen")
                  : t("composition.none");
          const on = selected === segment.index;
          return (
            <button
              key={segment.index}
              type="button"
              role="option"
              aria-selected={on}
              aria-label={t("segmentAria", {
                n: String(segment.index + 1),
                of: String(draft.segments.length),
                start: formatClock(segment.t_start),
                end: formatClock(segment.t_end),
                summary,
              })}
              onClick={() => {
                onSelect(segment.index);
                onPlayhead((segment.t_start + segment.t_end) / 2);
              }}
              className={`shrink-0 snap-start rounded-full px-3 py-1 font-mono text-xs uppercase tracking-[0.08em] ${
                on ? "bg-[color:var(--bg-inverse)] text-[color:var(--text-inverse)]" : "border border-[color:var(--line-strong)]"
              }`}
            >
              {formatRange(segment.t_start, segment.t_end)} · {summary}
            </button>
          );
        })}
      </div>
      {trimEnabled && (
        <div className="mt-4" data-testid="analysis-window">
          <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-3">
            <p className="cs-eyebrow">{t("layout.trim.label")}</p>
            <p className="font-mono text-xs uppercase tracking-[0.08em]">
              {formatClock(windowSpan.start_s)} – {formatClock(windowSpan.end_s)} · {formatClock(duration)}
            </p>
          </div>
          <div
            ref={trackRef}
            className="relative h-8"
            onPointerDown={(event) => {
              if ((event.target as HTMLElement).dataset.trim) return;
              onPlayhead(timeAt(event.clientX));
            }}
          >
            <div className="absolute inset-x-0 top-3 h-2 bg-[color:var(--bg-muted)]" />
            <div
              className="absolute top-3 h-2 bg-[color:var(--text-strong)]"
              style={{
                left: `${(windowSpan.start_s / duration) * 100}%`,
                width: `${((windowSpan.end_s - windowSpan.start_s) / duration) * 100}%`,
              }}
            />
            <span
              className="absolute top-1 h-6 w-px bg-[color:var(--status-warning)]"
              style={{ left: `${(playhead / duration) * 100}%` }}
              aria-hidden="true"
            />
            <button
              type="button"
              data-trim="start"
              aria-label={t("layout.trim.start")}
              data-testid="trim-start"
              className="absolute top-0 h-11 w-6 -translate-x-1/2 border border-[color:var(--text-strong)] bg-[color:var(--bg)]"
              style={{ left: `${(windowSpan.start_s / duration) * 100}%` }}
              onPointerDown={(event) => dragHandle("start", event)}
            />
            <button
              type="button"
              data-trim="end"
              aria-label={t("layout.trim.end")}
              data-testid="trim-end"
              className="absolute top-0 h-11 w-6 -translate-x-1/2 border border-[color:var(--text-strong)] bg-[color:var(--bg)]"
              style={{ left: `${(windowSpan.end_s / duration) * 100}%` }}
              onPointerDown={(event) => dragHandle("end", event)}
            />
          </div>
          <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{t("layout.trim.help")}</p>
          {message && (
            <p role="status" className="mt-1 text-sm text-[color:var(--status-warning)]">
              {message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
