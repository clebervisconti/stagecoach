"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  defaultEnabledLanes,
  itemAtTime,
  playheadPercent,
  spriteUrl,
  timeFromClick,
  type TimelineLane,
  type TimelineLaneId,
  type TimelinePayload,
} from "@/lib/timeline";

type TimelineProps = {
  sessionId: string;
  payload: TimelinePayload | null;
  currentTime: number;
  focusedLaneId: string | null;
  onFocusLane: (id: string) => void;
  onSeek: (time: number) => void;
};

const LANE_I18N: Record<TimelineLaneId, string> = {
  sections: "laneSections",
  slides: "laneSlides",
  fillers: "laneFillers",
  long_pauses: "lanePauses",
  rushing: "laneRushing",
  monotone: "laneMonotone",
  gestures: "laneGestures",
  audience_facing: "laneFacing",
  smiles: "laneSmiles",
  clt_story: "laneClt",
  qa: "laneQa",
};

export function ReportTimeline({
  sessionId,
  payload,
  currentTime,
  focusedLaneId,
  onFocusLane,
  onSeek,
}: TimelineProps) {
  const t = useTranslations("report");
  const [enabled, setEnabled] = useState<Set<string> | null>(null);
  const [hover, setHover] = useState<{ t: number; label: string } | null>(null);
  const duration = payload?.duration_s ?? 0;
  const lanes = payload?.lanes ?? [];
  const on = enabled ?? defaultEnabledLanes(payload);
  const visible = useMemo(
    () => lanes.filter((lane) => on.has(lane.id) && (lane.available || lane.items.length > 0)),
    [lanes, on],
  );

  if (!payload || duration <= 0) {
    return (
      <p className="mt-3 text-xs text-muted-foreground" data-testid="timeline-empty">
        {t("timelineUnavailable")}
      </p>
    );
  }

  function toggle(id: string) {
    setEnabled((prev) => {
      const next = new Set(prev ?? defaultEnabledLanes(payload));
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function seekFromEvent(event: { clientX: number; currentTarget: HTMLElement }) {
    const rect = event.currentTarget.getBoundingClientRect();
    onSeek(timeFromClick(event.clientX, rect, duration));
  }

  return (
    <section className="mt-4" data-testid="timeline" aria-label={t("timeline")}>
      <div className="mb-2 flex flex-wrap gap-2" data-testid="timeline-toggles">
        {lanes.map((lane) => (
          <label key={lane.id} className="inline-flex items-center gap-1 text-xs">
            <input
              type="checkbox"
              checked={on.has(lane.id)}
              disabled={!lane.available && lane.items.length === 0}
              onChange={() => toggle(lane.id)}
              aria-label={laneLabel(t, lane)}
            />
            {laneLabel(t, lane)}
            {lane.opt_in ? ` (${t("optIn")})` : ""}
          </label>
        ))}
      </div>
      <div
        className="relative space-y-1 rounded-md border bg-muted/40 p-2"
        onClick={seekFromEvent}
        onKeyDown={() => undefined}
      >
        {visible.map((lane) => (
          <button
            key={lane.id}
            type="button"
            data-testid={`timeline-lane-${lane.id}`}
            aria-pressed={focusedLaneId === lane.id}
            aria-label={laneLabel(t, lane)}
            onClick={(event) => {
              event.stopPropagation();
              onFocusLane(lane.id);
              seekFromEvent(event);
            }}
            className={`relative h-6 w-full overflow-hidden rounded-sm text-left ${
              focusedLaneId === lane.id ? "ring-2 ring-ring" : "bg-background/70"
            }`}
          >
            {lane.items.map((item, index) => {
              const left = playheadPercent(item.t_start, duration);
              const width = Math.max(0.4, playheadPercent(item.t_end, duration) - left);
              const active = itemAtTime(lane, currentTime) === item;
              return (
                <span
                  key={`${lane.id}-${index}`}
                  className={`absolute top-1 h-4 rounded-sm ${active ? "bg-primary" : "bg-primary/50"}`}
                  style={{ left: `${left}%`, width: `${width}%` }}
                  title={item.label}
                  onMouseEnter={() => setHover({ t: item.t_start, label: item.label })}
                  onMouseLeave={() => setHover(null)}
                />
              );
            })}
          </button>
        ))}
        <div
          className="pointer-events-none absolute bottom-2 top-2 w-px bg-foreground"
          style={{ left: `${playheadPercent(currentTime, duration)}%` }}
          data-testid="timeline-playhead"
        />
      </div>
      {hover && (
        <div className="mt-2 flex items-center gap-3 text-xs" data-testid="timeline-hover">
          <img
            src={spriteUrl(sessionId, hover.t)}
            alt=""
            width={160}
            height={90}
            className="h-[90px] w-[160px] rounded-sm bg-black object-cover"
          />
          <p>{hover.label}</p>
        </div>
      )}
      <p className="mt-2 text-xs text-muted-foreground">{t("timelineHelp")}</p>
    </section>
  );
}

function laneLabel(t: ReturnType<typeof useTranslations>, lane: TimelineLane): string {
  const key = LANE_I18N[lane.id as TimelineLaneId];
  return key ? t(key) : lane.id.replaceAll("_", " ");
}
