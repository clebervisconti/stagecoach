"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle2, Loader2, Trash2 } from "lucide-react";

type SessionDetail = {
  id: string;
  title: string;
  status: string;
  job: null | {
    status: string;
    error: { message?: string } | null;
    steps: Array<{ stage: string; status: string }>;
  };
};

type Report = {
  partial: boolean;
  overall: number | null;
  confidence: number;
  coverage: number;
  summary: string;
  duration_s: number;
  quality: { snr_db: number | null; warnings: string[] };
  metrics: Array<{
    id: string;
    label: string;
    value: number | null;
    unit: string;
    score: number | null;
    confidence: number;
    source: string;
  }>;
  strengths: Array<{ metric_id: string; title: string; score: number }>;
  opportunities: Array<{
    metric_id: string;
    title: string;
    score: number;
    evidence_ids: string[];
  }>;
  evidence: Array<{
    id: string;
    t_start: number;
    t_end: number;
    text: string;
    confidence: number;
  }>;
  transcript: Array<{ id: number; start: number; end: number; text: string }>;
  series: Array<{ t: number; pitch_st: number | null; intensity_db: number | null }>;
};

function PitchGraph({ series }: { series: Report["series"] }) {
  const points = useMemo(() => {
    const valid = series.filter((point) => point.pitch_st !== null);
    if (valid.length < 2) return "";
    const maxT = Math.max(...valid.map((point) => point.t), 1);
    const values = valid.map((point) => point.pitch_st as number);
    const min = Math.min(...values, -1);
    const max = Math.max(...values, 1);
    const range = Math.max(max - min, 1);
    return valid
      .map((point) => `${(point.t / maxT) * 600},${120 - (((point.pitch_st as number) - min) / range) * 100}`)
      .join(" ");
  }, [series]);
  if (!points) return <p className="text-sm text-muted-foreground">No pitch series available.</p>;
  return (
    <svg viewBox="0 0 600 140" role="img" aria-label="Pitch variation over time" className="h-40 w-full">
      <line x1="0" y1="120" x2="600" y2="120" className="stroke-border" />
      <polyline points={points} fill="none" className="stroke-primary" strokeWidth="3" />
    </svg>
  );
}

export default function SessionPage() {
  const t = useTranslations("report");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionsPath = locale === "en" ? "/sessions" : `/${locale}/sessions`;
  const mediaRef = useRef<HTMLVideoElement>(null);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const terminal = session?.status === "ready" || session?.status === "partial" || session?.status === "failed";

  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const response = await fetch(`/api/stagecoach/sessions/${params.id}`, { cache: "no-store" });
        if (!response.ok) throw new Error(t("loadError"));
        const body: SessionDetail = await response.json();
        if (!active) return;
        setSession(body);
        if ((body.status === "ready" || body.status === "partial") && !report) {
          const reportResponse = await fetch(`/api/stagecoach/sessions/${params.id}/report`, {
            cache: "no-store",
          });
          if (reportResponse.ok) setReport(await reportResponse.json());
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : t("loadError"));
      }
    }
    void refresh();
    const timer = window.setInterval(() => {
      if (!terminal) void refresh();
    }, 2500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [params.id, report, terminal, t]);

  function seek(time: number) {
    if (!mediaRef.current) return;
    mediaRef.current.currentTime = Math.max(0, time);
    void mediaRef.current.play();
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
    return <div className="flex min-h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div>;
  }

  return (
    <div className="container mx-auto space-y-8 px-4 py-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <button onClick={() => router.push(sessionsPath)} className="mb-3 text-sm text-primary hover:underline">
            ← {t("back")}
          </button>
          <h1 className="text-3xl font-bold">{session?.title}</h1>
          <p className="mt-2 text-sm text-muted-foreground capitalize">
            {session?.status} {report?.partial ? `· ${t("partial")}` : ""}
          </p>
        </div>
        <button
          onClick={remove}
          className="inline-flex items-center gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive hover:bg-destructive/10"
        >
          <Trash2 className="h-4 w-4" /> {t("delete")}
        </button>
      </div>

      {error && <div role="alert" className="rounded-md bg-destructive/10 p-4 text-destructive">{error}</div>}

      {!terminal && (
        <section className="rounded-lg border bg-card p-6">
          <div className="mb-5 flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <h2 className="text-xl font-semibold">{t("processing")}</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            {["ingest", "asr", "audio_features", "report"].map((stage) => {
              const complete = session?.job?.steps.some((step) => step.stage === stage && step.status === "succeeded");
              return (
                <div key={stage} className="flex items-center gap-2 rounded-md bg-muted p-3 text-sm">
                  {complete ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : <Loader2 className="h-4 w-4 animate-spin" />}
                  {t(stage)}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {session?.status === "failed" && (
        <section className="rounded-lg border border-destructive/40 bg-destructive/10 p-6">
          <div className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-5 w-5" /> {t("failed")}</div>
          <p className="mt-2 text-sm">{session.job?.error?.message || t("failedHelp")}</p>
        </section>
      )}

      {report && (
        <>
          <section className="grid gap-4 md:grid-cols-[220px_1fr]">
            <div className="rounded-lg border bg-card p-6 text-center">
              <div className="text-sm text-muted-foreground">{t("measuredScore")}</div>
              <div className="mt-2 text-6xl font-bold">{report.overall ?? "—"}</div>
              <div className="mt-3 text-xs text-muted-foreground">
                {t("confidence")}: {Math.round(report.confidence * 100)}% · {t("coverage")}:{" "}
                {Math.round(report.coverage * 100)}%
              </div>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <h2 className="text-xl font-semibold">{t("summary")}</h2>
              <p className="mt-3 leading-7 text-muted-foreground">{report.summary}</p>
              {report.quality.warnings.map((warning) => (
                <p key={warning} className="mt-3 flex items-center gap-2 text-sm text-amber-700">
                  <AlertTriangle className="h-4 w-4" /> {warning}
                </p>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-4 text-2xl font-semibold">{t("metrics")}</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {report.metrics.map((metric) => (
                <div key={metric.id} className="rounded-lg border bg-card p-5">
                  <div className="text-sm text-muted-foreground">{metric.label}</div>
                  <div className="mt-2 text-3xl font-bold">
                    {metric.value ?? "—"} <span className="text-sm font-normal">{metric.unit}</span>
                  </div>
                  <div className="mt-3 text-xs text-muted-foreground">
                    {t("score")}: {metric.score ?? "N/A"} · {t("confidence")}:{" "}
                    {Math.round(metric.confidence * 100)}% · {metric.source}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-6 md:grid-cols-2">
            <div className="rounded-lg border bg-card p-6">
              <h2 className="text-xl font-semibold">{t("strengths")}</h2>
              <ul className="mt-4 space-y-3">
                {report.strengths.length ? report.strengths.map((item) => (
                  <li key={item.metric_id} className="rounded-md bg-green-500/10 p-3">
                    {item.title} <span className="text-sm text-muted-foreground">({item.score})</span>
                  </li>
                )) : <li className="text-sm text-muted-foreground">{t("noStrengthsYet")}</li>}
              </ul>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <h2 className="text-xl font-semibold">{t("opportunities")}</h2>
              <ul className="mt-4 space-y-3">
                {report.opportunities.map((item) => (
                  <li key={item.metric_id} className="rounded-md bg-primary/10 p-3">
                    {item.title} <span className="text-sm text-muted-foreground">({item.score})</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section className="rounded-lg border bg-card p-6">
            <h2 className="text-xl font-semibold">{t("pitchGraph")}</h2>
            <PitchGraph series={report.series} />
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold">{t("recording")}</h2>
              <video
                ref={mediaRef}
                controls
                preload="metadata"
                className="w-full rounded-md bg-black"
                src={`/api/stagecoach/sessions/${params.id}/media`}
              />
              <div className="mt-4 space-y-2">
                {report.evidence.slice(0, 12).map((item) => (
                  <button
                    key={item.id}
                    onClick={() => seek(item.t_start)}
                    className="block w-full rounded-md border p-3 text-left text-sm hover:border-primary"
                  >
                    <span className="font-mono text-xs text-primary">{item.t_start.toFixed(1)}s</span>{" "}
                    {item.text}
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold">{t("transcript")}</h2>
              <div className="max-h-[560px] space-y-3 overflow-y-auto pr-2">
                {report.transcript.map((segment) => (
                  <button
                    key={segment.id}
                    onClick={() => seek(segment.start)}
                    className="block w-full rounded-md p-2 text-left hover:bg-muted"
                  >
                    <span className="mr-2 font-mono text-xs text-primary">{segment.start.toFixed(1)}s</span>
                    {segment.text}
                  </button>
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
