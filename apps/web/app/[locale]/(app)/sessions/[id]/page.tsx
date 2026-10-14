"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, Loader2, Trash2 } from "lucide-react";
import type { AnalysisReport } from "@/lib/report-types";
import { CategoryCards } from "@/components/report/category-cards";
import { InsightsPanel } from "@/components/report/insights-panel";
import { KeyMetrics } from "@/components/report/key-metrics";
import { ReportPlayer } from "@/components/report/player";
import { RadarChart } from "@/components/report/radar-chart";
import { SummaryCard } from "@/components/report/summary-card";
import { TranscriptTab } from "@/components/report/transcript-tab";
import { VoiceTab } from "@/components/report/voice-tab";
import { eventsUrl, parseProgressData, shouldReloadReport } from "@/lib/progress";
import { radarPoints } from "@/lib/report-view";
import { exportVtt, type TranscriptPayload } from "@/lib/transcript";
import type { SeriesPayload } from "@/lib/voice-charts";

type SessionDetail = {
  id: string;
  title: string;
  status: string;
  context_type: string;
  language: string;
  slot_min: number | null;
  created_at: string;
  job: null | {
    status: string;
    error: { message?: string } | null;
    steps: Array<{ stage: string; status: string }>;
  };
};

const FALLBACK_STAGES = [
  "ingest",
  "asr",
  "audio_features",
  "partial_scoring",
  "fusion_scoring",
  "report",
];
const STAGE_LABELS = new Set([
  "ingest",
  "asr",
  "audio_features",
  "partial_scoring",
  "fusion_scoring",
  "content_llm",
  "report",
]);

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
  const [tab, setTab] = useState<"categories" | "transcript" | "voice">("categories");
  const seekRef = useRef<(tStart: number) => void>(() => undefined);
  const [error, setError] = useState("");
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
      if (shouldReloadReport(event)) void loadArtifacts();
      if (event?.type === "done") void refresh();
    };
    return () => {
      active = false;
      window.clearInterval(timer);
      source.close();
    };
  }, [params.id, terminal, t]);

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
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  const stages =
    session?.job?.steps.length
      ? session.job.steps.map((step) => step.stage)
      : FALLBACK_STAGES;
  const durationMin = report?.media?.duration_s ? report.media.duration_s / 60 : null;
  const slotLabel =
    session?.slot_min && durationMin
      ? `${session.slot_min} ${t("minutes")} → ${durationMin.toFixed(1)} ${t("minutes")}`
      : session?.slot_min
        ? `${session.slot_min} ${t("minutes")}`
        : null;

  return (
    <div className="container mx-auto space-y-8 px-4 py-8">
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
          <p className="mt-2 text-sm text-muted-foreground">
            {session?.created_at ? new Date(session.created_at).toLocaleString(locale) : ""}
            {session?.context_type ? ` · ${session.context_type.replaceAll("_", " ")}` : ""}
            {session?.language ? ` · ${session.language}` : ""}
            {slotLabel ? ` · ${t("slotVsActual")}: ${slotLabel}` : ""}
            {report?.overall.partial ? ` · ${t("partial")}` : ""}
          </p>
        </div>
        <button
          type="button"
          data-testid="delete-session"
          onClick={remove}
          className="inline-flex items-center gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" /> {t("delete")}
        </button>
      </div>

      {error && (
        <div role="alert" className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error}
        </div>
      )}

      {!terminal && (
        <section className="rounded-lg border bg-card p-6" data-testid="processing">
          <div className="mb-5 flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <h2 className="text-xl font-semibold">{t("processing")}</h2>
          </div>
          <p className="mb-4 text-sm text-muted-foreground">{t("processingHint")}</p>
          <div className="grid gap-3 md:grid-cols-4">
            {stages.map((stage) => {
              const complete = session?.job?.steps.some(
                (step) => step.stage === stage && step.status === "succeeded",
              );
              const label = STAGE_LABELS.has(stage)
                ? t(
                    stage as
                      | "ingest"
                      | "asr"
                      | "audio_features"
                      | "partial_scoring"
                      | "fusion_scoring"
                      | "content_llm"
                      | "report",
                  )
                : stage.replaceAll("_", " ");
              return (
                <div key={stage} className="flex items-center gap-2 rounded-md bg-muted p-3 text-sm">
                  {complete ? (
                    <span className="h-2 w-2 rounded-full bg-emerald-600" aria-hidden="true" />
                  ) : (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  {label}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {session?.status === "failed" && (
        <section className="rounded-lg border border-destructive/40 bg-destructive/10 p-6">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-5 w-5" /> {t("failed")}
          </div>
          <p className="mt-2 text-sm">{session.job?.error?.message || t("failedHelp")}</p>
        </section>
      )}

      {report && (
        <div data-testid="report">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <SummaryCard report={report} />
            <section className="rounded-lg border bg-card p-6">
              <RadarChart points={radarPoints(report)} />
            </section>
          </div>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <ReportPlayer
              sessionId={params.id}
              evidence={report.evidence ?? []}
              captionsVtt={transcript ? exportVtt(transcript) : undefined}
              seekRef={seekRef}
            />
            <KeyMetrics report={report} />
          </div>
          <InsightsPanel report={report} onSeek={(time) => seekRef.current(time)} />
          <div>
            <div role="tablist" aria-label={t("tabs")} className="mb-4 flex flex-wrap gap-2">
              {(["categories", "transcript", "voice"] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                  className={`rounded-full px-4 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    tab === id ? "bg-primary text-primary-foreground" : "bg-muted"
                  }`}
                >
                  {t(id === "categories" ? "categories" : id === "transcript" ? "transcript" : "voiceTab")}
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
          </div>
        </div>
      )}
    </div>
  );
}
