"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Check, X } from "lucide-react";
import { elapsedClock, formatClock, parseServerInstant } from "@/lib/online";
import type { StepSnapshot } from "@/lib/progress";

export function PreparingPanel({
  title,
  posterUrl,
  previewT,
  durationS,
  steps,
  startedAt,
  activity,
  etaMinutes,
  onPosterError,
  failed,
  skipReview,
}: {
  title: string;
  posterUrl: string | null;
  previewT?: number | null;
  durationS?: number | null;
  steps: StepSnapshot[];
  startedAt: string | null;
  activity?: string | null;
  etaMinutes?: number | null;
  onPosterError?: () => void;
  failed?: string | null;
  skipReview?: boolean;
}) {
  const t = useTranslations("online");
  const locale = useLocale();
  const newHref = locale === "en" ? "/sessions/new" : `/${locale}/sessions/new`;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (failed) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [failed]);

  const ingest = steps.find((step) => step.stage === "ingest");
  const layout = steps.find((step) => step.stage === "layout");
  const layoutRunning = layout?.status === "running" || (ingest?.status === "succeeded" && !layout);
  const scan = layoutRunning;

  const startedMs = parseServerInstant(startedAt);
  const elapsed = startedAt ? elapsedClock(startedAt, now) : "0:00";
  const slow = Boolean(startedMs != null && now - startedMs > 60_000);

  const rows = [
    {
      id: "media",
      status: ingest?.status === "succeeded" ? "done" : ingest?.status === "failed" ? "failed" : ingest ? "running" : "pending",
      title: t("prepMedia"),
      detail:
          ingest?.status === "succeeded"
          ? durationS
            ? t("prepMediaDone", { duration: formatClock(durationS) })
            : t("prepMediaReady")
          : activity || t("prepMediaHint"),
      time: ingest?.status === "succeeded" ? "—" : null,
    },
    {
      id: "layout",
      status: layout?.status === "succeeded" ? "done" : layoutRunning ? "running" : "pending",
      title: t("prepFinding"),
      detail: t("prepFindingHint"),
    },
    {
      id: "review",
      status: "pending",
      title: skipReview ? t("prepStart") : t("prepCheck"),
      detail: skipReview ? t("prepStartHint") : t("prepCheckHint"),
    },
  ] as const;

  return (
    <section data-testid="preparing" className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_400px]">
      <figure className="relative overflow-hidden bg-[color:var(--bg-subtle)]">
        <div className="relative aspect-video">
          {posterUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={posterUrl}
              alt=""
              data-testid="session-poster"
              className="h-full w-full object-cover"
              onError={onPosterError}
            />
          ) : (
            <div
              data-testid="poster-placeholder"
              className="flex h-full items-center justify-center text-sm text-[color:var(--text-tertiary)]"
            >
              {title}
            </div>
          )}
          <span className="pointer-events-none absolute left-2 top-2 h-3 w-3 border-l border-t border-[color:var(--text-on-media)] opacity-60" />
          <span className="pointer-events-none absolute right-2 top-2 h-3 w-3 border-r border-t border-[color:var(--text-on-media)] opacity-60" />
          <span className="pointer-events-none absolute bottom-2 left-2 h-3 w-3 border-b border-l border-[color:var(--text-on-media)] opacity-60" />
          <span className="pointer-events-none absolute bottom-2 right-2 h-3 w-3 border-b border-r border-[color:var(--text-on-media)] opacity-60" />
          {scan && (
            <span className="cs-scan-line pointer-events-none absolute inset-x-0 top-0 h-px bg-[color:var(--line-strong)]" />
          )}
        </div>
        <figcaption className="mt-2 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
          {previewT != null ? t("frameAt", { time: formatClock(previewT) }) : t("previewOnly")}
        </figcaption>
      </figure>

      <div className="rounded-[var(--radius-sm)] border border-[color:var(--line)] p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="cs-eyebrow">{failed ? t("couldntPrepare") : t("preparingTitle")}</h2>
            {!failed && <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{t("usuallyMinute")}</p>}
          </div>
          {!failed && (
            <div className="text-right">
              <p data-testid="elapsed" className="font-mono text-sm tabular-nums">
                {elapsed}
              </p>
              {etaMinutes != null && (
                <p data-testid="prep-eta" className="mt-1 text-xs text-[color:var(--text-secondary)]">
                  {t("aboutLeft", { n: etaMinutes })}
                </p>
              )}
            </div>
          )}
        </div>

        {failed ? (
          <div
            role="alert"
            data-testid="prepare-error"
            className="mt-6 rounded-[var(--radius-sm)] border border-[color:var(--status-critical)] p-4"
          >
            <p className="flex items-start gap-2 text-sm">
              <X className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--status-critical)]" aria-hidden="true" />
              <span>
                <span className="font-display text-xs font-bold uppercase tracking-[0.08em] text-[color:var(--status-critical)]">
                  {t("couldntRead")}
                </span>
                <span className="text-[color:var(--text)]"> · {t("couldntReadHelp")}</span>
              </span>
            </p>
            <a
              href={newHref}
              data-testid="upload-another"
              className="mt-4 inline-flex h-11 items-center rounded-[var(--radius-sm)] bg-[color:var(--action-primary)] px-5 text-xs uppercase tracking-[0.08em] text-[color:var(--text-inverse)]"
            >
              {t("uploadAnother")}
            </a>
          </div>
        ) : (
          <ol className="mt-6 space-y-2" aria-live="polite">
            {rows.map((row) => (
              <li
                key={row.id}
                className={`rounded-[var(--radius-sm)] px-3 py-3 ${row.status === "running" ? "bg-[color:var(--bg-muted)]" : ""}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <StatusMark status={row.status} />
                    <div>
                      <p className={row.status === "pending" ? "text-[color:var(--text-tertiary)]" : "font-medium"}>
                        {row.title}
                        <span className="sr-only">
                          {row.status === "done" ? t("done") : row.status === "running" ? t("inProgress") : t("notStarted")}
                        </span>
                      </p>
                      <p
                        className="mt-1 text-sm text-[color:var(--text-secondary)]"
                        data-testid={row.id === "media" && activity ? "prep-activity" : undefined}
                      >
                        {row.detail}
                      </p>
                    </div>
                  </div>
                  {"time" in row && row.time ? <p className="font-mono text-xs tabular-nums">{row.time}</p> : null}
                </div>
              </li>
            ))}
          </ol>
        )}

        {slow && !failed && <p className="mt-4 text-sm text-[color:var(--text-secondary)]">{t("stillWorkingPrep")}</p>}
        <p className="mt-6 text-sm text-[color:var(--text-secondary)]">{t("leavePage")}</p>
      </div>
    </section>
  );
}

function StatusMark({ status }: { status: string }) {
  if (status === "done") {
    return <Check className="mt-0.5 h-4 w-4 text-[color:var(--text-secondary)]" aria-hidden="true" />;
  }
  if (status === "running") {
    return <span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-[color:var(--text-strong)]" aria-hidden="true" />;
  }
  return <span className="mt-1.5 h-2.5 w-2.5 rounded-full border border-[color:var(--text-tertiary)]" aria-hidden="true" />;
}
