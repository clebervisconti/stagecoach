"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { AnalysisReport } from "@/lib/report-types";
import type { SlideCard } from "@/lib/body-slides";
import { formatTimestamp } from "@/lib/player";
import {
  cameraGaps,
  clusterMarkers,
  defaultZoom,
  filterCounts,
  isLongSession,
  markersFor,
  matchesFilters,
  metricValue,
  screenFlowView,
  screenTime,
  virtualWindow,
  ZOOM_MINUTES,
  type FlowFilter,
  type ScreenDocument,
  type ScreenSegment,
} from "@/lib/screen-flow";
import { CategoryCard } from "./category-cards";

const ROW_HEIGHT = 72;
const MARK = { talkOver: "▲", deadAir: "■", silentDemo: "◆", prompt: "●" } as const;

type Props = {
  report: AnalysisReport;
  document: ScreenDocument | null;
  loading: boolean;
  error: boolean;
  sessionStatus?: string | null;
  steps?: { stage: string; status: string }[];
  deckSlides?: SlideCard[];
  playhead: number;
  sessionId: string;
  onSeek: (time: number) => void;
  onRetry: () => void;
};

export function ScreenFlowTab(props: Props) {
  const t = useTranslations("online");
  const mode = props.report.session?.delivery_mode;
  const view = screenFlowView({
    deliveryMode: mode,
    loading: props.loading,
    error: props.error,
    payload: props.document,
    steps: props.steps,
    sessionStatus: props.sessionStatus,
    deckPages: props.deckSlides?.length ?? 0,
  });
  const categories = props.report.categories ?? [];
  const cards = ["screen_flow", "online_engagement"]
    .map((id) => categories.find((category) => category.id === id))
    .filter((category) => category != null);

  return (
    <div data-testid="screen-flow-tab" className="grid gap-6">
      {view === "loading" && (
        <div data-testid="screen-flow-loading" aria-busy="true" className="grid gap-3">
          <div className="h-8 rounded bg-[color:var(--bg-subtle)]" />
          <div className="h-24 rounded bg-[color:var(--bg-subtle)]" />
          <div className="h-40 rounded bg-[color:var(--bg-subtle)]" />
        </div>
      )}
      {view === "processing" && (
        <div data-testid="screen-flow-processing" className="grid gap-3">
          <p className="text-sm">{t("screenFlow.processing.title")}</p>
          <p className="text-sm text-[color:var(--text-secondary)]">{t("screenFlow.processing.body")}</p>
          <div aria-busy="true" className="h-24 rounded bg-[color:var(--bg-subtle)]" />
        </div>
      )}
      {view === "error" && (
        <div role="alert" data-testid="screen-flow-error" className="rounded-md border border-destructive p-4">
          <p className="font-medium">{t("screenFlow.error.title")}</p>
          <p className="mt-1 text-sm text-[color:var(--text-secondary)]">{t("screenFlow.error.body")}</p>
          <button type="button" className="mt-3 underline" onClick={props.onRetry}>
            {t("screenFlow.error.retry")}
          </button>
        </div>
      )}
      {view === "empty" && (
        <div data-testid="screen-flow-empty" className="rounded-md border p-6 text-center">
          <p>{t("screenFlow.empty.body")}</p>
          <a className="mt-3 inline-block underline" href={`/sessions/${props.sessionId}/layout`}>
            {t("screenFlow.empty.cta")}
          </a>
        </div>
      )}
      {view === "deck" && (
        <div data-testid="screen-flow-deck" className="grid gap-3">
          <p className="text-sm">{t("screenFlow.deckOnly.title")}</p>
          <p className="text-sm text-[color:var(--text-secondary)]">{t("screenFlow.deckOnly.body")}</p>
          <ul className="grid gap-2">
            {(props.deckSlides ?? []).map((slide) => (
              <li key={slide.index} className="rounded border px-3 py-2 text-sm">
                {t("screenFlow.type.page")} {slide.index + 1}
                {slide.title ? ` · ${slide.title}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      {view === "ready" && props.document && (
        <ReadyView
          document={props.document}
          mode={mode || "webinar"}
          playhead={props.playhead}
          onSeek={props.onSeek}
        />
      )}
      {view !== "loading" && view !== "hidden" && (
        <section className="grid gap-3 md:grid-cols-2">
          <p className="md:col-span-2 text-right font-mono text-xs text-[color:var(--text-tertiary)]">
            {t("screenFlow.scoringConfig")} {props.report.provenance?.scoring_config_version ?? "1.1.0"}
          </p>
          {cards.map((category) => (
            <CategoryCard key={category.id} category={category} report={props.report} onSeek={props.onSeek} />
          ))}
        </section>
      )}
      {view === "ready" && <Coaching document={props.document} onSeek={props.onSeek} />}
      {view === "error" && props.document?.coaching && <Coaching document={props.document} onSeek={props.onSeek} />}
    </div>
  );
}

function ReadyView({
  document,
  mode,
  playhead,
  onSeek,
}: {
  document: ScreenDocument;
  mode: string;
  playhead: number;
  onSeek: (time: number) => void;
}) {
  const t = useTranslations("online");
  const segments = document.segments ?? [];
  const [filters, setFilters] = useState<FlowFilter[]>([]);
  const [selected, setSelected] = useState(segments[0]?.id ?? "");
  const [open, setOpen] = useState<string | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [zoomWidth, setZoomWidth] = useState(15 * 60);
  const duration = Math.max(document.duration_s || 0, segments.at(-1)?.t_end || 0, screenTime(document));
  const long = isLongSession(
    segments.length,
    duration,
    800,
    Math.min(...segments.map((segment) => Math.max(0.01, segment.t_end - segment.t_start))),
  );
  const firstFlag = segments.find((segment) => (segment.flags ?? []).length > 0)?.t_start ?? null;
  const zoom = long ? { ...defaultZoom(duration, firstFlag), width: zoomWidth } : { start: 0, width: duration || 1 };
  const counts = filterCounts(segments);
  const visible = segments.filter((segment) => matchesFilters(segment, filters));
  const rowWindow = virtualWindow(visible.length, scrollTop, 480, ROW_HEIGHT);
  const slice = visible.slice(rowWindow.start, rowWindow.end);
  const markers = markersFor(document).filter((marker) => {
    if (filters.length === 0) return true;
    return filters.some((filter) => marker.kind.toLowerCase().includes(filter === "talkOver" ? "talk" : filter.slice(0, 4)));
  });
  const groups = clusterMarkers(markers, 800, duration || 1);
  const gaps = cameraGaps(segments, duration);

  function toggle(filter: FlowFilter) {
    setFilters((current) => (current.includes(filter) ? current.filter((item) => item !== filter) : [...current, filter]));
  }

  function choose(segment: ScreenSegment) {
    setSelected(segment.id);
    onSeek(segment.t_start);
  }

  const chips: { id: "all" | FlowFilter; label: string }[] = [
    { id: "all", label: t("screenFlow.filters.all", { count: counts.all }) },
    { id: "long", label: t("screenFlow.filters.long", { count: counts.long }) },
    { id: "rushed", label: t("screenFlow.filters.rushed", { count: counts.rushed }) },
    { id: "silent", label: t("screenFlow.filters.silent", { count: counts.silent }) },
    { id: "talkOver", label: t("screenFlow.filters.talkOver", { count: counts.talkOver }) },
  ];

  return (
    <div data-testid="screen-flow-ready" className="grid gap-5">
      <header>
        <p className="font-mono text-xs uppercase tracking-wide text-[color:var(--text-tertiary)]">
          {t("screenFlow.eyebrow", { mode, count: segments.length })}
        </p>
        <h2 className="mt-2 text-xl font-semibold">{t("screenFlow.insight.title")}</h2>
        <p className="mt-1 max-w-3xl text-sm text-[color:var(--text-secondary)]">{t("screenFlow.insight.body")}</p>
      </header>
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label={t("screenFlow.kpi.screens")} value={String(segments.length)} />
        <Kpi label={t("screenFlow.kpi.clean")} value={percent(metricValue(document.metrics, "sf_clean_transition_ratio"))} />
        <Kpi label={t("screenFlow.kpi.aligned")} value={percent(metricValue(document.metrics, "sf_narration_alignment_ratio"))} />
        {mode === "online_talk" ? (
          <Kpi label={t("screenFlow.kpi.signposted")} value={percent(metricValue(document.metrics, "sf_signpost_ratio"))} />
        ) : (
          <Kpi label={t("screenFlow.kpi.lead")} value={seconds(metricValue(document.metrics, "sf_narration_lead_s_median"))} />
        )}
        <Kpi label={t("screenFlow.kpi.deadAir")} value={number(metricValue(document.metrics, "sf_dead_air_per_10min"))} />
      </dl>
      <div data-testid="flow-strip" role="group" aria-label={t("screenFlow.strip.label", { count: segments.length })}>
        <p className="mb-2 font-mono text-xs text-[color:var(--text-secondary)]">
          {t("screenFlow.strip.screenTime", {
            screen: formatTimestamp(screenTime(document)),
            total: formatTimestamp(duration),
          })}
        </p>
        <div className="relative h-6">
          {groups.map((group) => {
            const marker = group[0];
            const left = duration > 0 ? (marker.t / duration) * 100 : 0;
            return (
              <button
                key={marker.id}
                type="button"
                className="absolute top-0 h-6 w-6 -translate-x-1/2 text-xs"
                style={{ left: `${left}%`, color: "var(--flow-marker-color)" }}
                aria-label={t(`screenFlow.legend.${marker.kind}`)}
                onClick={() => onSeek(marker.t)}
              >
                {MARK[marker.kind]}
                {group.length > 1 ? group.length : ""}
              </button>
            );
          })}
        </div>
        <div className="relative h-10 rounded" style={{ background: "var(--bg)" }}>
          {gaps.map((gap) => (
            <span
              key={`${gap.t_start}-${gap.t_end}`}
              aria-hidden="true"
              className="absolute inset-y-0"
              style={{
                left: `${(gap.t_start / (duration || 1)) * 100}%`,
                width: `${((gap.t_end - gap.t_start) / (duration || 1)) * 100}%`,
                background: "repeating-linear-gradient(45deg, transparent, transparent 3px, var(--flow-gap-hatch) 3px, var(--flow-gap-hatch) 4px)",
              }}
            />
          ))}
          {segments.map((segment, index) => {
            const match = matchesFilters(segment, filters);
            const active = segment.id === selected || (playhead >= segment.t_start && playhead < segment.t_end);
            const left = ((segment.t_start - zoom.start) / zoom.width) * 100;
            const width = ((segment.t_end - segment.t_start) / zoom.width) * 100;
            if (left > 100 || left + width < 0) return null;
            return (
              <button
                key={segment.id}
                type="button"
                data-testid="flow-block"
                aria-pressed={active}
                aria-label={t("screenFlow.strip.block", {
                  index: index + 1,
                  type: segment.type || "SLIDE",
                  start: formatTimestamp(segment.t_start),
                  end: formatTimestamp(segment.t_end),
                })}
                className="absolute inset-y-0"
                style={{
                  left: `${Math.max(0, left)}%`,
                  width: `${Math.max(0.4, width)}%`,
                  background: active ? "var(--flow-block-fill-selected)" : "var(--flow-block-fill)",
                  boxShadow: "inset 0 0 0 1px var(--flow-block-edge)",
                  opacity: match ? 1 : 0.4,
                }}
                onClick={() => choose(segment)}
              />
            );
          })}
          <span
            data-testid="flow-playhead"
            aria-hidden="true"
            className="absolute inset-y-0 w-0.5"
            style={{
              left: `${((playhead - zoom.start) / zoom.width) * 100}%`,
              background: "var(--flow-playhead)",
            }}
          />
        </div>
        {long && (
          <div className="mt-2 flex items-center gap-2">
            <button type="button" className="h-9 w-11 border" onClick={() => setZoomWidth(stepZoom(zoomWidth, -1))} aria-label={t("screenFlow.long.zoomOut")}>
              −
            </button>
            <button type="button" className="h-9 w-11 border" onClick={() => setZoomWidth(stepZoom(zoomWidth, 1))} aria-label={t("screenFlow.long.zoomIn")}>
              +
            </button>
            <span className="font-mono text-xs">{t("screenFlow.long.zoomHint")}</span>
          </div>
        )}
      </div>
      <div>
        <div className="mb-2 flex gap-2 overflow-x-auto">
          {chips.map((chip) => {
            const count = counts[chip.id];
            const pressed = chip.id === "all" ? filters.length === 0 : filters.includes(chip.id);
            const disabled = chip.id !== "all" && count === 0;
            return (
              <button
                key={chip.id}
                type="button"
                aria-pressed={pressed}
                disabled={disabled}
                className="h-8 shrink-0 rounded-full border px-3 text-xs disabled:text-[color:var(--text-tertiary)]"
                onClick={() => {
                  if (chip.id === "all") setFilters([]);
                  else toggle(chip.id);
                }}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
        <p role="status" className="font-mono text-xs text-[color:var(--text-secondary)]">
          {t("screenFlow.filters.status", { shown: visible.length, total: segments.length })}
          {filters.length > 0 && (
            <button type="button" className="ml-2 underline" onClick={() => setFilters([])}>
              {t("screenFlow.filters.clear")}
            </button>
          )}
        </p>
        <div
          data-testid="screen-list"
          className="mt-2 h-[480px] overflow-auto"
          onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
        >
          <div role="grid" aria-rowcount={visible.length} style={{ height: visible.length * ROW_HEIGHT, position: "relative" }}>
            {slice.map((segment, offset) => {
              const index = rowWindow.start + offset;
              const shared = segment.narration?.shared_terms?.length ?? 0;
              const narration = segment.narration?.aligned
                ? t("screenFlow.narration.aligned", { count: shared })
                : shared > 0
                  ? t("screenFlow.narration.notAligned", { count: shared })
                  : t("screenFlow.narration.notEligible");
              return (
                <div
                  key={segment.id}
                  role="row"
                  aria-rowindex={index + 1}
                  data-testid="screen-row"
                  className="absolute inset-x-0 grid items-center gap-2 border-b px-2 text-sm"
                  style={{
                    top: index * ROW_HEIGHT,
                    height: open === segment.id ? undefined : ROW_HEIGHT,
                    minHeight: ROW_HEIGHT,
                    gridTemplateColumns: "96px 36px 76px 1fr 24px",
                    background: segment.id === selected ? "var(--screen-row-selected)" : undefined,
                    boxShadow: segment.id === selected ? "inset 2px 0 0 var(--text-strong)" : undefined,
                  }}
                >
                  <div role="gridcell">
                    {segment.keyframe_url ? (
                      // Signed screen-region keyframe from the API. Not a camera crop.
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={segment.keyframe_url} alt="" width={96} height={54} className="h-[54px] w-24 object-cover" />
                    ) : (
                      <span className="block h-[54px] w-24 bg-[color:var(--bg-subtle)]" />
                    )}
                  </div>
                  <div role="gridcell" className="font-mono text-xs">{index + 1}</div>
                  <div role="gridcell" className="font-mono text-[11px] uppercase">{typeLabel(t, segment.type)}</div>
                  <div role="gridcell" className="min-w-0">
                    <button
                      type="button"
                      className="w-full truncate text-left"
                      aria-expanded={open === segment.id}
                      onClick={() => {
                        choose(segment);
                        setOpen((current) => (current === segment.id ? null : segment.id));
                      }}
                    >
                      <span className="font-mono text-xs">
                        {formatTimestamp(segment.t_start)}–{formatTimestamp(segment.t_end)}
                      </span>
                      <span className="mt-1 block truncate text-[color:var(--text-secondary)]">{narration}</span>
                      <FlagLine segment={segment} />
                    </button>
                    {open === segment.id && (
                      <div className="pb-2 text-sm">
                        <p className="font-mono text-xs">
                          {t("screenFlow.excerpt.label", {
                            start: formatTimestamp(segment.t_start),
                            end: formatTimestamp(segment.t_end),
                          })}
                        </p>
                        <p className="mt-1">{narration}</p>
                        <p className="mt-1 text-xs text-[color:var(--text-secondary)]">{t("screenFlow.excerpt.legend")}</p>
                        <button type="button" className="mt-2 underline" onClick={() => onSeek(segment.t_start)}>
                          {t("screenFlow.excerpt.play", { time: formatTimestamp(segment.t_start) })}
                        </button>
                      </div>
                    )}
                  </div>
                  <div role="gridcell" aria-hidden="true">›</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function Coaching({ document, onSeek }: { document: ScreenDocument | null; onSeek: (time: number) => void }) {
  const t = useTranslations("online");
  const coaching = document?.coaching;
  if (!coaching) return null;
  const fallback = Boolean(coaching.fallback) || coaching.source === "template";
  return (
    <section data-testid="flow-coaching" className="grid gap-3">
      <h3 className="text-lg font-semibold">{t("screenFlow.coaching.title")}</h3>
      {fallback ? (
        <p data-testid="flow-coaching-fallback" className="text-sm">
          {t("screenFlow.coaching.fallbackBody")}
        </p>
      ) : (
        <p className="font-mono text-xs text-[color:var(--text-tertiary)]">{t("screenFlow.coaching.source")}</p>
      )}
      <ol className="grid gap-2">
        {(coaching.observations ?? []).map((item, index) => (
          <li key={`${item.title}-${index}`}>
            <p className="font-medium">{item.title}</p>
            {item.detail && <p className="text-sm text-[color:var(--text-secondary)]">{item.detail}</p>}
            <button type="button" className="text-sm underline" onClick={() => onSeek(item.t || 0)}>
              {t("screenFlow.excerpt.play", { time: formatTimestamp(item.t || 0) })}
            </button>
          </li>
        ))}
      </ol>
      <h4 className="font-medium">{t("screenFlow.coaching.drills")}</h4>
      <ol className="grid gap-2">
        {(coaching.drills ?? []).map((drill, index) => (
          <li key={drill.title}>
            {t("screenFlow.coaching.drill", { n: index + 1, minutes: drill.practice_time_min ?? 10 })} {drill.title}. {drill.how}
          </li>
        ))}
      </ol>
      <h4 className="font-medium">{t("screenFlow.coaching.keep")}</h4>
      <ul>
        {(coaching.strengths ?? []).map((item) => (
          <li key={item.title}>{item.title}</li>
        ))}
      </ul>
      <p className="text-sm text-[color:var(--text-secondary)]">
        {t("screenFlow.coaching.footer")}{" "}
        <Link className="underline" href="/research">
          {t("screenFlow.coaching.howWeMeasure")}
        </Link>
      </p>
    </section>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-[color:var(--text-tertiary)]">{label}</dt>
      <dd className="font-mono text-lg">{value}</dd>
    </div>
  );
}

function FlagLine({ segment }: { segment: ScreenSegment }) {
  const flags = segment.flags ?? [];
  if (flags.length === 0) return null;
  return <span className="mt-1 block font-mono text-[11px] uppercase">{flags.join(" · ")}</span>;
}

function typeLabel(t: (key: string) => string, type: string | undefined): string {
  const key = (type || "slide").toLowerCase();
  if (key === "slide" || key === "demo" || key === "video" || key === "idle" || key === "page") {
    return t(`screenFlow.type.${key}`);
  }
  return type || "";
}

function percent(value: number | null): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function seconds(value: number | null): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)} s`;
}

function number(value: number | null): string {
  if (value == null) return "—";
  return String(Math.round(value * 10) / 10);
}

function stepZoom(current: number, direction: number): number {
  const index = Math.max(0, ZOOM_MINUTES.findIndex((minutes) => minutes * 60 === current));
  const next = Math.min(ZOOM_MINUTES.length - 1, Math.max(0, index + direction));
  return ZOOM_MINUTES[next] * 60;
}
