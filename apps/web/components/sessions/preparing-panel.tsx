"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, X } from "lucide-react";
import { formatClock } from "@/lib/online";
import type { StepSnapshot } from "@/lib/progress";

export function PreparingPanel({
  title,
  posterUrl,
  previewT,
  durationS,
  steps,
  startedAt,
  failed,
  skipReview,
}: {
  title: string;
  posterUrl: string | null;
  previewT?: number | null;
  durationS?: number | null;
  steps: StepSnapshot[];
  startedAt: string | null;
  failed?: string | null;
  skipReview?: boolean;
}) {
  const t = useTranslations("online");
  const [now, setNow] = useState(() => Date.now());
  const [scan, setScan] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const ingest = steps.find((step) => step.stage === "ingest");
  const layout = steps.find((step) => step.stage === "layout");
  const layoutRunning = layout?.status === "running" || (ingest?.status === "succeeded" && !layout);
  useEffect(() => {
    if (layoutRunning) setScan(true);
  }, [layoutRunning]);

  const elapsed = startedAt ? formatClock((now - new Date(startedAt).getTime()) / 1000) : "0:00";
  const slow = Boolean(startedAt && now - new Date(startedAt).getTime() > 60_000);

  const rows = [
    {
      id: "media",
      status: ingest?.status === "succeeded" ? "done" : ingest?.status === "failed" ? "failed" : ingest ? "running" : "pending",
      title: t("prepMedia"),
      detail: ingest?.status === "succeeded" ? t("prepMediaDone", { duration: durationS ? formatClock(durationS) : "—" }) : t("prepMediaHint"),
      time: ingest?.status === "succeeded" ? formatClock(9) : null,
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
            <img src={posterUrl} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-[color:var(--text-tertiary)]">
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
          {t("frameAt", { time: previewT != null ? formatClock(previewT) : "—" })}
        </figcaption>
      </figure>

      <div className="rounded-[var(--radius-sm)] border border-[color:var(--line)] p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="cs-eyebrow">{t("preparingTitle")}</h2>
            <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{t("usuallyMinute")}</p>
          </div>
          <p className="font-mono text-sm tabular-nums">{elapsed}</p>
        </div>

        {failed ? (
          <div role="alert" className="mt-6 rounded-[var(--radius-sm)] border border-[color:var(--status-critical)] p-4">
            <p className="flex items-center gap-2 text-sm text-[color:var(--status-critical)]">
              <X className="h-4 w-4" aria-hidden="true" />
              {t("couldntRead")}
            </p>
            <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{t("couldntReadHelp")}</p>
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
                      <p className="mt-1 text-sm text-[color:var(--text-secondary)]">{row.detail}</p>
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
