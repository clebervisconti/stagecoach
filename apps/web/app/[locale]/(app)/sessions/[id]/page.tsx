"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, FileDown, Trash2 } from "lucide-react";
import type { AnalysisReport } from "@/lib/report-types";
import { CategoryCards } from "@/components/report/category-cards";
import { InsightsPanel } from "@/components/report/insights-panel";
import { KeyMetrics } from "@/components/report/key-metrics";
import { ReportPlayer } from "@/components/report/player";
import { RadarChart } from "@/components/report/radar-chart";
import { SummaryCard } from "@/components/report/summary-card";
import { BodyTab } from "@/components/report/body-tab";
import { ObjectivesTab, type CoachingPayload } from "@/components/report/objectives-tab";
import { SlidesTab } from "@/components/report/slides-tab";
import { TranscriptTab } from "@/components/report/transcript-tab";
import { VoiceTab } from "@/components/report/voice-tab";
import type { BodyPayload, SlidesPayload } from "@/lib/body-slides";
import { exportFileUrl, exportStatusUrl, exportUrl } from "@/lib/pdf-export";
import { formatTimestamp } from "@/lib/player";
import { eventsUrl, parseProgressData, shouldReloadReport, type StageProgressEvent, type StepSnapshot } from "@/lib/progress";
import { ProcessingTimeline } from "@/components/report/processing-timeline";
import { NotMeasured } from "@/components/report/not-measured";
import { PreparingPanel } from "@/components/sessions/preparing-panel";
import { WizardStepper } from "@/components/sessions/new/wizard-stepper";
import { formatClock, type DeliveryMode } from "@/lib/online";
import { Globe, Mic, Play, Users } from "lucide-react";
import { goalRadarPoints, radarPoints, type GoalLike } from "@/lib/report-view";
import { exportVtt, type TranscriptPayload } from "@/lib/transcript";
import type { TimelinePayload } from "@/lib/timeline";
import type { SeriesPayload } from "@/lib/voice-charts";

type SessionDetail = {
  id: string;
  title: string;
  status: string;
  context_type: string;
  delivery_mode?: string;
  source_kind?: string;
  language: string;
  slot_min: number | null;
  created_at: string;
  media?: { duration_s?: number | null } | null;
  job: null | {
    status: string;
    error: { message?: string } | null;
    created_at?: string;
    steps: StepSnapshot[];
  };
};

function isAutoConfirmed(steps: StepSnapshot[] | undefined): boolean {
  return Boolean(
    steps?.some(
      (step) =>
        step.stage === "layout_review" &&
        step.status === "succeeded" &&
        (step.detail === "confirmed_automatically" || step.message === "Confirmed automatically"),
    ),
  );
}

function isConsentOff(steps: StepSnapshot[] | undefined): boolean {
  return Boolean(
    steps?.some(
      (step) =>
        step.problem === "consent_video_off" ||
        (step.status === "skipped" &&
          (step.stage === "layout" || step.stage === "layout_review" || step.stage === "vision" || step.stage === "region_crops")),
    ),
  );
}

function isReport(value: unknown): value is AnalysisReport {
  if (!value || typeof value !== "object") return false;
  const candidate = value as AnalysisReport;
  return Boolean(candidate.overall && candidate.pillars && candidate.categories && candidate.insights);
}

export default function SessionPage() {
  const t = useTranslations("report");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionsPath = locale === "en" ? "/sessions" : `/${locale}/sessions`;
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [transcript, setTranscript] = useState<TranscriptPayload | null>(null);
  const [series, setSeries] = useState<Record<string, SeriesPayload | null>>({});
  const [timeline, setTimeline] = useState<TimelinePayload | null>(null);
  const [body, setBody] = useState<BodyPayload | null>(null);
  const [slides, setSlides] = useState<SlidesPayload | null>(null);
  const [goals, setGoals] = useState<GoalLike[]>([]);
  const [coaching, setCoaching] = useState<CoachingPayload | null>(null);
  const [tab, setTab] = useState<
    "categories" | "transcript" | "voice" | "timeline" | "body" | "slides" | "objectives"
  >("categories");
  const seekRef = useRef<(tStart: number) => void>(() => undefined);
  const [live, setLive] = useState<StageProgressEvent | null>(null);
  const [error, setError] = useState("");
  const [includeTranscript, setIncludeTranscript] = useState(false);
  const [exporting, setExporting] = useState(false);
  const terminal = session?.status === "ready" || session?.status === "partial" || session?.status === "failed";

  useEffect(() => {
    let active = true;
    async function loadArtifacts() {
      const reportResponse = await fetch(`/api/stagecoach/sessions/${params.id}/report`, {
        cache: "no-store",
      });
      if (reportResponse.ok) {
        const payload: unknown = await reportResponse.json();
        if (isReport(payload) && active) setReport(payload);
      }
      const transcriptResponse = await fetch(`/api/stagecoach/sessions/${params.id}/transcript`, {
        cache: "no-store",
      });
      if (transcriptResponse.ok && active) setTranscript(await transcriptResponse.json());
      const seriesNames = ["pace", "pitch", "loudness", "energy"] as const;
      const loaded: Record<string, SeriesPayload | null> = {};
      await Promise.all(
        seriesNames.map(async (name) => {
          const response = await fetch(`/api/stagecoach/sessions/${params.id}/series/${name}`, {
            cache: "no-store",
          });
          loaded[name] = response.ok ? ((await response.json()) as SeriesPayload) : null;
        }),
      );
      if (active) setSeries(loaded);
      const timelineResponse = await fetch(`/api/stagecoach/sessions/${params.id}/timeline`, {
        cache: "no-store",
      });
      if (timelineResponse.ok && active) {
        setTimeline((await timelineResponse.json()) as TimelinePayload);
      }
      const coachingResponse = await fetch(`/api/stagecoach/sessions/${params.id}/coaching`, {
        cache: "no-store",
      });
      if (coachingResponse.ok && active) {
        setCoaching((await coachingResponse.json()) as CoachingPayload);
      }
      const bodyResponse = await fetch(`/api/stagecoach/sessions/${params.id}/body`, {
        cache: "no-store",
      });
      if (bodyResponse.ok && active) {
        setBody((await bodyResponse.json()) as BodyPayload);
      }
      const slidesResponse = await fetch(`/api/stagecoach/sessions/${params.id}/slides`, {
        cache: "no-store",
      });
      if (slidesResponse.ok && active) {
        setSlides((await slidesResponse.json()) as SlidesPayload);
      }
      const goalsResponse = await fetch("/api/stagecoach/goals", { cache: "no-store" });
      if (goalsResponse.ok && active) {
        const payload = (await goalsResponse.json()) as { goals?: GoalLike[] };
        setGoals(payload.goals ?? []);
      }
    }
    async function refresh() {
      try {
        const response = await fetch(`/api/stagecoach/sessions/${params.id}`, { cache: "no-store" });
        if (!response.ok) throw new Error(t("loadError"));
        const body: SessionDetail = await response.json();
        if (!active) return;
        setSession(body);
        const ready = body.status === "ready" || body.status === "partial";
        if (ready || body.status === "processing") {
          await loadArtifacts();
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : t("loadError"));
      }
    }
    void refresh();
    const timer = window.setInterval(() => {
      if (!terminal) void refresh();
    }, 2500);
    const source = new EventSource(eventsUrl(params.id));
    source.onmessage = (message) => {
      if (!active) return;
      const event = parseProgressData(message.data);
      if (event?.type === "stage") setLive(event);
      if (shouldReloadReport(event)) void loadArtifacts();
      if (event?.type === "done") void refresh();
    };
    return () => {
      active = false;
      window.clearInterval(timer);
      source.close();
    };
  }, [params.id, terminal, t]);

  async function exportPdf() {
    setExporting(true);
    setError("");
    try {
      const created = await fetch(exportUrl(params.id), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ include_transcript: includeTranscript }),
      });
      if (!created.ok) throw new Error(t("exportError"));
      const body = (await created.json()) as { id: string };
      for (let i = 0; i < 20; i += 1) {
        const statusResponse = await fetch(exportStatusUrl(body.id), { cache: "no-store" });
        if (!statusResponse.ok) throw new Error(t("exportError"));
        const status = (await statusResponse.json()) as { status: string };
        if (status.status === "ready") {
          window.location.assign(exportFileUrl(body.id));
          return;
        }
        if (status.status === "failed") throw new Error(t("exportError"));
        await new Promise((resolve) => window.setTimeout(resolve, 400));
      }
      throw new Error(t("exportError"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("exportError"));
    } finally {
      setExporting(false);
    }
  }

  async function remove() {
    if (!window.confirm(t("deleteConfirm"))) return;
    const response = await fetch(`/api/stagecoach/sessions/${params.id}`, { method: "DELETE" });
    if (!response.ok) {
      setError(t("deleteError"));
      return;
    }
    router.push(sessionsPath);
  }

  if (!session && !error) {
    return <SessionSkeleton />;
  }

  const showPrepare =
    session?.status === "preparing" ||
    session?.status === "layout_review" ||
    (session?.status === "failed" && !report);
  const durationS = session?.media?.duration_s ?? report?.media?.duration_s ?? null;
  const durationMin = durationS ? durationS / 60 : null;
  const slotLabel =
    session?.slot_min && durationMin
      ? `${session.slot_min} ${t("minutes")} → ${durationMin.toFixed(1)} ${t("minutes")}`
      : null;
  const autoConfirmed = isAutoConfirmed(session?.job?.steps);
  const consentOff = isConsentOff(session?.job?.steps);
  const layoutDone =
    Boolean(session?.job?.steps?.some((step) => step.stage === "layout_review" && (step.status === "succeeded" || step.status === "skipped"))) ||
    session?.status === "processing" ||
    session?.status === "ready" ||
    session?.status === "partial";

  return (
    <div className="container mx-auto space-y-8 px-4 py-8">
      {session?.delivery_mode && session.delivery_mode !== "stage" && (showPrepare || session.status === "processing") && (
        <WizardStepper
          mode={session.delivery_mode as DeliveryMode}
          current="layout"
          layoutDone={layoutDone}
          autoConfirmed={autoConfirmed}
          consentOff={consentOff}
          onSelect={(id) => {
            if (id === "layout" && session) router.push(`${sessionsPath}/${session.id}/layout`);
          }}
        />
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button
            type="button"
            onClick={() => router.push(sessionsPath)}
            className="mb-3 text-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            ← {t("back")}
          </button>
          <h1 className="text-3xl font-bold">{session?.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            {session?.delivery_mode && session.delivery_mode !== "stage" && (
              <ModeBadge
                mode={session.delivery_mode as DeliveryMode}
                kinds={report?.layout_summary?.kinds}
                camera={report?.layout_summary?.camera_visible_ratio}
                screen={report?.layout_summary?.screen_visible_ratio}
                compact={showPrepare || !report}
              />
            )}
            <p className="font-mono text-xs uppercase tracking-[0.08em]">
              {sessionMeta(session?.created_at, locale, report?.media?.duration_s, session?.language)}
              {slotLabel ? ` · ${t("slotVsActual")}: ${slotLabel}` : ""}
              {report?.overall.partial ? ` · ${t("partial")}` : ""}
            </p>
          </div>
        </div>
        {!showPrepare && (
        <div className="flex flex-col items-end gap-2">
          {report && (
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  data-testid="include-transcript"
                  checked={includeTranscript}
                  onChange={(event) => setIncludeTranscript(event.target.checked)}
                />
                {t("includeTranscript")}
              </label>
              <button
                type="button"
                data-testid="export-pdf"
                onClick={() => void exportPdf()}
                disabled={exporting}
                className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <FileDown className="h-4 w-4" aria-hidden="true" />
                {exporting ? t("exportQueued") : t("exportPdf")}
              </button>
            </div>
          )}
        <button
          type="button"
          data-testid="delete-session"
          onClick={remove}
          className="inline-flex items-center gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" /> {t("delete")}
        </button>
        </div>
        )}
      </div>

      {error && (
        <div role="alert" className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error}
        </div>
      )}

      {showPrepare && session && (
        <PreparingPanel
          title={session.title}
          posterUrl={`/api/stagecoach/sessions/${session.id}/poster`}
          durationS={durationS}
          steps={session.job?.steps ?? []}
          startedAt={session.job?.created_at ?? session.created_at}
          failed={session.status === "failed" ? session.job?.error?.message || "unreadable" : null}
          skipReview={autoConfirmed}
        />
      )}

      {session?.status === "layout_review" && (
        <div role="status" className="rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] p-4">
          <a href={`${sessionsPath}/${session.id}/layout`} className="text-xs uppercase tracking-[0.08em]">
            Check the layout
          </a>
          <p className="mt-2 text-sm text-[color:var(--text-secondary)]">
            Confirm the layout before we analyse this recording.
          </p>
        </div>
      )}

      {!terminal && session && !showPrepare && (
        <ProcessingTimeline
          steps={session.job?.steps ?? []}
          live={live}
          startedAt={session.job?.created_at ?? session.created_at}
          deliveryMode={session.delivery_mode}
          sourceKind={session.source_kind}
          sessionStatus={session.status}
          autoConfirmed={autoConfirmed}
          consentOff={consentOff}
        />
      )}

      {terminal && session && !showPrepare && (
        <ProcessingTimeline
          mode="notes"
          steps={session.job?.steps ?? []}
          live={live}
          startedAt={null}
        />
      )}

      {session?.status === "failed" && !showPrepare && (
        <section className="rounded-lg border border-destructive/40 bg-destructive/10 p-6">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-5 w-5" /> {t("failed")}
          </div>
          <p className="mt-2 text-sm">{session.job?.error?.message || t("failedHelp")}</p>
        </section>
      )}

      {report && !showPrepare && (
        <div data-testid="report" className="space-y-8">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <SummaryCard report={report} />
            <section className="rounded-lg border bg-card p-6">
              <RadarChart
                points={radarPoints(report)}
                goalPoints={goalRadarPoints(radarPoints(report), goals)}
              />
            </section>
          </div>
          <InsightsPanel report={report} onSeek={(time) => seekRef.current(time)} />
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <ReportPlayer
              sessionId={params.id}
              evidence={report.evidence ?? []}
              captionsVtt={transcript ? exportVtt(transcript) : undefined}
              seekRef={seekRef}
              timeline={timeline}
            />
            <KeyMetrics report={report} />
          </div>
          <NotMeasured report={report} />
          <div>
            <div role="tablist" aria-label={t("tabs")} className="mb-4 flex flex-wrap gap-2">
              {(
                [
                  "categories",
                  "transcript",
                  "voice",
                  "timeline",
                  ...(session?.delivery_mode && session.delivery_mode !== "stage" ? [] : (["body"] as const)),
                  "slides",
                  "objectives",
                ] as const
              ).map((id) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                  className={`border-b-2 bg-transparent px-3 py-2 text-xs tracking-[0.08em] ${
                    tab === id ? "border-current text-foreground" : "border-transparent text-muted-foreground"
                  }`}
                >
                  {t(
                    id === "categories"
                      ? "categories"
                      : id === "transcript"
                        ? "transcript"
                        : id === "voice"
                          ? "voiceTab"
                          : id === "timeline"
                            ? "timeline"
                            : id === "body"
                              ? "bodyTab"
                              : id === "slides"
                                ? "slidesTab"
                                : "objectivesTab",
                  )}
                </button>
              ))}
            </div>
            {tab === "categories" && (
              <CategoryCards report={report} onSeek={(time) => seekRef.current(time)} />
            )}
            {tab === "transcript" && (
              <TranscriptTab payload={transcript} onSeek={(time) => seekRef.current(time)} />
            )}
            {tab === "voice" && (
              <VoiceTab
                transcript={transcript}
                contextType={session?.context_type ?? report.session?.context_type}
                pace={series.pace ?? null}
                pitch={series.pitch ?? null}
                loudness={series.loudness ?? null}
                energy={series.energy ?? null}
                onSeek={(time) => seekRef.current(time)}
              />
            )}
            {tab === "body" && <BodyTab payload={body} onSeek={(time) => seekRef.current(time)} />}
            {tab === "objectives" && <ObjectivesTab payload={coaching} />}
            {tab === "slides" && (
              <SlidesTab
                sessionId={params.id}
                payload={slides}
                onSeek={(time) => seekRef.current(time)}
              />
            )}
            {tab === "timeline" && (
              <div data-testid="timeline-tab">
                <p className="mb-3 text-sm text-muted-foreground">{t("timelineTabHint")}</p>
                <table className="w-full text-sm">
                  <caption className="sr-only">{t("timeline")}</caption>
                  <thead>
                    <tr>
                      <th className="text-left">{t("timeline")}</th>
                      <th className="text-left">{t("evidence")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(timeline?.lanes ?? []).flatMap((lane) =>
                      lane.items.map((item, index) => (
                        <tr key={`${lane.id}-${index}`}>
                          <td>{lane.id.replaceAll("_", " ")}</td>
                          <td>
                            <button
                              type="button"
                              className="text-primary underline"
                              onClick={() => seekRef.current(item.t_start)}
                            >
                              ▶ {formatTimestamp(item.t_start)} {item.label}
                            </button>
                          </td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function sessionMeta(
  createdAt: string | undefined,
  locale: string,
  durationS?: number | null,
  language?: string | null,
): string {
  const parts: string[] = [];
  if (createdAt) {
    parts.push(new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short", year: "numeric" }).format(new Date(createdAt)));
  }
  if (durationS) parts.push(formatClock(durationS));
  if (language) parts.push(language.replace("pt-BR", "PT-BR").toUpperCase());
  return parts.join(" · ");
}

function SessionSkeleton() {
  return (
    <div className="container mx-auto space-y-8 px-4 py-8" data-testid="session-skeleton">
      <div className="h-4 w-24 bg-[color:var(--bg-muted)]" />
      <div className="h-10 w-72 bg-[color:var(--bg-muted)]" />
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="aspect-video bg-[color:var(--bg-muted)]" />
        <div className="h-64 bg-[color:var(--bg-muted)]" />
      </div>
    </div>
  );
}

function ModeBadge({
  mode,
  kinds,
  camera,
  screen,
  compact = false,
}: {
  mode: DeliveryMode;
  kinds?: string[];
  camera?: number | null;
  screen?: number | null;
  compact?: boolean;
}) {
  const Icon = mode === "stage" ? Mic : mode === "webinar" ? Users : mode === "online_talk" ? Globe : Play;
  const hasCamera = (camera ?? 0) > 0 || kinds?.some((kind) => kind.includes("camera") || kind === "composite");
  const hasScreen = (screen ?? 0) > 0 || kinds?.some((kind) => kind.includes("screen") || kind === "composite");
  const t = useTranslations("online");
  const half =
    hasCamera && hasScreen
      ? t("composition.cameraScreen")
      : hasCamera
        ? t("composition.camera")
        : hasScreen
          ? t("composition.screen")
          : t("composition.none");
  const label = t(`modes.${mode}.title`);
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-[color:var(--line-strong)] px-3 py-1 text-xs uppercase tracking-[0.08em] text-[color:var(--text-strong)]"
      aria-label={compact ? `Mode: ${label.toLowerCase()}` : `Mode: ${label.toLowerCase()}, ${half.toLowerCase()}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {compact ? label : `${label} · ${half}`}
    </span>
  );
}
