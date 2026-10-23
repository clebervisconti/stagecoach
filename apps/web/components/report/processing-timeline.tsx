"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Check, CircleX, Info } from "lucide-react";
import {
  pipelineTimeline,
  type StageProgressEvent,
  type StepSnapshot,
} from "@/lib/progress";

const STAGE_KEYS = [
  "ingest",
  "asr",
  "alignment",
  "audio_features",
  "partial_scoring",
  "vision",
  "slides",
  "content_llm",
  "fusion_scoring",
  "report",
  "layout",
  "layout_review",
  "production_quality",
  "region_crops",
  "sync",
  "camera_presence",
  "screen_flow",
] as const;

type StageKey = (typeof STAGE_KEYS)[number];

function isStageKey(stage: string): stage is StageKey {
  return (STAGE_KEYS as readonly string[]).includes(stage);
}

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function stageLabel(
  stage: string,
  deliveryMode: string,
  t: (key: StageKey | "visionOnline" | "slidesOnline" | "audioFeaturesOnline" | "layoutCheck") => string,
  consentOff = false,
): string {
  if (consentOff && stage === "layout") return t("layoutCheck");
  if (deliveryMode !== "stage") {
    if (stage === "vision") return t("visionOnline");
    if (stage === "slides") return t("slidesOnline");
    if (stage === "audio_features") return t("audioFeaturesOnline");
  }
  return isStageKey(stage) ? t(stage) : stage.replaceAll("_", " ");
}

export function ProcessingTimeline({
  steps,
  live,
  startedAt,
  mode = "live",
  deliveryMode = "stage",
  sourceKind = "upload",
  autoConfirmed = false,
  sessionStatus,
  consentOff = false,
}: {
  steps: StepSnapshot[];
  live: StageProgressEvent | null;
  startedAt: string | null;
  mode?: "live" | "notes";
  deliveryMode?: string;
  sourceKind?: string;
  autoConfirmed?: boolean;
  sessionStatus?: string;
  consentOff?: boolean;
}) {
  const t = useTranslations("report");
  const locale = useLocale();
  const settingsHref = `${locale === "en" ? "" : `/${locale}`}/settings#video-analysis`;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const stages = pipelineTimeline(steps, live, {
    deliveryMode,
    sourceKind,
    sessionStatus: sessionStatus ?? (mode === "notes" ? "ready" : undefined),
    layoutConfirmed: autoConfirmed ? "auto" : "user",
  });
  const current = stages.find((stage) => stage.status === "running" || stage.status === "waiting");
  const elapsed = startedAt ? formatElapsed(now - new Date(startedAt).getTime()) : null;
  const slow = Boolean(current && startedAt && now - new Date(startedAt).getTime() > 90_000);
  const problems = stages.filter(
    (stage) => stage.status === "failed" || (stage.status === "skipped" && stage.problem !== "consent_video_off"),
  );
  const visible = stages;

  if (mode === "notes") {
    if (!problems.length) return null;
    return (
      <div className="rounded-[var(--radius-sm)] border border-[color:var(--status-warning)] bg-[color:var(--status-warning-subtle)] p-4" data-testid="stage-log">
        <h2 className="text-sm font-semibold">{t("activityLog")}</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {problems.map((stage) => (
            <li key={stage.stage}>
              <span className="font-medium">{stageLabel(stage.stage, deliveryMode, t, consentOff)}</span>
              {": "}
              {stage.problem ? t(stage.problem) : stage.detail || t("stageSkipped")}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <section className="rounded-[var(--radius-sm)] border bg-card p-6" data-testid="processing">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--text-strong)]" aria-hidden="true" />
            <h2 className="text-xl font-semibold">{t("processing")}</h2>
          </div>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            {current
              ? t("stageRunning", {
                  stage: stageLabel(current.stage, deliveryMode, t, consentOff),
                })
              : t("processingHint")}
          </p>
          {autoConfirmed && !consentOff && (
            <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{t("layoutAuto")}</p>
          )}
        </div>
        {elapsed && (
          <p className="font-mono text-sm tabular-nums">
            {t("elapsed", { time: elapsed })}
          </p>
        )}
      </div>

      {slow && <p className="mt-4 font-mono text-sm text-muted-foreground">{t("stillWorking")}</p>}

      {consentOff && (
        <p data-testid="consent-off" className="mt-4 flex items-start gap-2 text-sm text-[color:var(--text-secondary)]">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            {t("consentOffLine")}{" "}
            <Link href={settingsHref} className="uppercase tracking-[0.08em]">
              {t("openSettings")}
            </Link>
          </span>
        </p>
      )}

      <ol className="mt-6 space-y-2">
        {visible.map((stage) => {
          const label = stageLabel(stage.stage, deliveryMode, t, consentOff);
          const resolvedDetail =
            stage.stage === "layout_review" && stage.status === "succeeded"
              ? stage.detail === "confirmed_automatically" || autoConfirmed
                ? t("layoutAuto")
                : t("layoutByYou")
              : stage.detail;
          const detail =
            stage.status === "skipped"
              ? t("skippedReason", {
                  reason:
                    stage.problem === "consent_video_off"
                      ? t("consentVideoOff")
                      : stage.problem
                        ? t(stage.problem)
                        : resolvedDetail || t("stageSkipped"),
                })
              : stage.problem
                ? t(stage.problem)
                : resolvedDetail;
          return (
            <li
              key={stage.stage}
              className={`flex items-start gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm ${
                stage.status === "running" ? "bg-[color:var(--bg-muted)]" : ""
              }`}
              data-stage={stage.stage}
              data-status={stage.status}
            >
              <span className="inline-flex w-4 shrink-0 justify-center">
                <StageMark status={stage.status} />
              </span>
              <div>
                <div className={stage.status === "pending" ? "text-muted-foreground" : "font-medium"}>
                  {label}
                </div>
                {detail && stage.status !== "pending" && (
                  <p className="mt-0.5 text-muted-foreground">{detail}</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {problems.length > 0 && (
        <div className="mt-6 rounded-[var(--radius-sm)] border border-[color:var(--status-warning)] bg-[color:var(--status-warning-subtle)] p-4" data-testid="stage-log">
          <h3 className="text-sm font-semibold">{t("activityLog")}</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {problems.map((stage) => (
              <li key={stage.stage}>
                <span className="font-medium">
                  {stageLabel(stage.stage, deliveryMode, t, consentOff)}
                </span>
                {": "}
                {stage.problem ? t(stage.problem) : stage.detail || t("stageSkipped")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function StageMark({ status }: { status: string }) {
  if (status === "succeeded") {
    return <Check className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--text-secondary)]" aria-hidden="true" />;
  }
  if (status === "failed") {
    return (
      <span className="mt-0.5 inline-flex items-center gap-1 text-[color:var(--status-critical)]">
        <CircleX className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span className="text-[11px] uppercase tracking-[0.08em]">Failed</span>
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="mt-0.5 font-mono text-[11px] uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
        —
      </span>
    );
  }
  if (status === "waiting") {
    return (
      <span className="mt-0.5 inline-flex items-center gap-1 text-[color:var(--text-secondary)]">
        <span aria-hidden="true">◐</span>
        <span className="text-[11px] uppercase tracking-[0.08em]">Waiting for you</span>
      </span>
    );
  }
  if (status === "running") {
    return <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-[color:var(--text-strong)]" aria-hidden="true" />;
  }
  return <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border border-muted-foreground/40" aria-hidden="true" />;
}
