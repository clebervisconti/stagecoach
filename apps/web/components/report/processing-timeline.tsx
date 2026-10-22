"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, Check, Loader2 } from "lucide-react";
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

export function ProcessingTimeline({
  steps,
  live,
  startedAt,
  mode = "live",
}: {
  steps: StepSnapshot[];
  live: StageProgressEvent | null;
  startedAt: string | null;
  mode?: "live" | "notes";
}) {
  const t = useTranslations("report");
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const stages = pipelineTimeline(steps, live);
  const current = stages.find((stage) => stage.status === "running");
  const elapsed = startedAt ? formatElapsed(now - new Date(startedAt).getTime()) : null;
  const slow = Boolean(
    current && startedAt && now - new Date(startedAt).getTime() > 90_000,
  );
  const problems = stages.filter((stage) => stage.status === "failed" || stage.status === "skipped");

  if (mode === "notes") {
    if (!problems.length) return null;
    return (
      <div className="rounded-xl border border-[color:var(--status-warning)] bg-[color:var(--status-warning-subtle)] p-4" data-testid="stage-log">
        <h2 className="text-sm font-semibold">{t("activityLog")}</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {problems.map((stage) => (
            <li key={stage.stage}>
              <span className="font-medium">
                {isStageKey(stage.stage) ? t(stage.stage) : stage.stage}
              </span>
              {": "}
              {stage.problem ? t(stage.problem) : stage.detail || t("stageSkipped")}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <section className="rounded-xl border bg-card p-6 shadow-sm" data-testid="processing">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <h2 className="text-xl font-semibold">{t("processing")}</h2>
          </div>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            {current
              ? t("stageRunning", {
                  stage: isStageKey(current.stage) ? t(current.stage) : current.stage,
                })
              : t("processingHint")}
          </p>
        </div>
        {elapsed && (
          <p className="rounded-full bg-muted px-3 py-1 text-sm font-medium tabular-nums">
            {t("elapsed", { time: elapsed })}
          </p>
        )}
      </div>

      {slow && <p className="mt-4 text-sm text-muted-foreground">{t("stillWorking")}</p>}

      <ol className="mt-6 space-y-2">
        {stages.map((stage) => {
          const label = isStageKey(stage.stage) ? t(stage.stage) : stage.stage.replaceAll("_", " ");
          const detail = stage.problem ? t(stage.problem) : stage.detail;
          return (
            <li
              key={stage.stage}
              className={`flex items-start gap-3 rounded-lg px-3 py-2 text-sm ${
                stage.status === "running" ? "bg-primary/10" : ""
              }`}
              data-stage={stage.stage}
              data-status={stage.status}
            >
              <StageMark status={stage.status} />
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
        <div className="mt-6 rounded-lg border border-[color:var(--status-warning)] bg-[color:var(--status-warning-subtle)] p-4" data-testid="stage-log">
          <h3 className="text-sm font-semibold">{t("activityLog")}</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {problems.map((stage) => (
              <li key={stage.stage}>
                <span className="font-medium">
                  {isStageKey(stage.stage) ? t(stage.stage) : stage.stage}
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
    return <Check className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--status-success)]" aria-hidden="true" />;
  }
  if (status === "failed") {
    return <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--status-critical)]" aria-hidden="true" />;
  }
  if (status === "running") {
    return <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden="true" />;
  }
  return <span className="mt-1 h-3 w-3 shrink-0 rounded-full border border-muted-foreground/40" aria-hidden="true" />;
}
