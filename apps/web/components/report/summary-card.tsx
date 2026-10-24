"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, Info } from "lucide-react";
import type { AnalysisReport } from "@/lib/report-types";
import { formatOverallLine, overallHeadline, overallLevelWord } from "@/lib/report-view";

type SummaryCardProps = {
  report: AnalysisReport;
};

export function SummaryCard({ report }: SummaryCardProps) {
  const t = useTranslations("report");
  const headline = overallHeadline(report);
  const levelName = headline.levelKey ? t(headline.levelKey) : null;
  const levelWord = overallLevelWord(headline.partial, levelName, t("partialBadge"));
  const line = formatOverallLine(headline.score, headline.band, levelWord);
  const warnings = report.quality?.warnings ?? [];
  const core = report.core_delivery?.score ?? null;
  const coreReady = typeof core === "number";

  return (
    <section className="rounded-[var(--radius-sm)] border bg-card p-6" aria-labelledby="report-summary-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="cs-eyebrow">{t("measuredScore")}</p>
          <p id="report-summary-heading" className="cs-stat mt-1 text-4xl md:text-6xl">
            {line}
          </p>
          <div className="mt-4 flex flex-wrap gap-4 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-secondary)]">
            <span>
              {t("coreDelivery")} {coreReady ? core : "—"}
              {!coreReady ? ` · ${t("coreDeliveryNeed")}` : ""}
            </span>
            <span>
              {t("coverage")} {Math.round(headline.coverage * 100)}%
            </span>
            <span>
              {t("confidence")} {Math.round(headline.confidence * 100)}%
            </span>
          </div>
        </div>
        {headline.partial && (
          <span
            className="cs-status-warning inline-flex items-center gap-1 px-3 py-1 text-sm"
            title={t("partialHint")}
          >
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
            {t("partialBadge")}
          </span>
        )}
      </div>
      <p className="mt-4 flex items-start gap-2 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{t("weightsHint")}</span>
      </p>
      {report.session?.delivery_mode && report.session.delivery_mode !== "stage" && (
        <p className="mt-2 text-sm text-muted-foreground">{t("coreDeliveryHint")}</p>
      )}
      <p className="mt-4 leading-7">
        {t("measuredSummary", {
          score: String(headline.score ?? "—"),
          ci: report.overall.display_band != null ? String(report.overall.display_band) : "—",
          n: report.categories.filter((category) => category.applicable && category.score != null).length,
          of: report.categories.length,
          m: report.categories.filter((category) => !category.applicable || category.score == null).length,
        })}
      </p>
      {warnings.map((warning) => (
        <p key={warning} className="mt-3 flex items-start gap-2 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--status-warning)]" aria-hidden="true" />
          <span>
            <span className="font-display text-xs font-bold uppercase tracking-[0.08em] text-[color:var(--status-warning)]">
              {t("lowConfidenceWord")}
            </span>
            <span className="text-[color:var(--text)]"> · {warning}</span>
          </span>
        </p>
      ))}
    </section>
  );
}
