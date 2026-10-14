"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, Info } from "lucide-react";
import type { AnalysisReport } from "@/lib/report-types";
import { formatOverallLine, overallHeadline } from "@/lib/report-view";

type SummaryCardProps = {
  report: AnalysisReport;
};

export function SummaryCard({ report }: SummaryCardProps) {
  const t = useTranslations("report");
  const headline = overallHeadline(report);
  const levelName = headline.levelKey ? t(headline.levelKey) : null;
  const line = formatOverallLine(headline.score, headline.band, levelName);
  const version = report.provenance?.scoring_config_version ?? "1.0.0";
  const warnings = report.quality?.warnings ?? [];

  return (
    <section className="rounded-lg border bg-card p-6" aria-labelledby="report-summary-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">{t("measuredScore")}</p>
          <p id="report-summary-heading" className="mt-1 text-4xl font-bold tracking-tight">
            {line}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("coverage")}: {Math.round(headline.coverage * 100)}% · {t("confidence")}:{" "}
            {Math.round(headline.confidence * 100)}%
          </p>
        </div>
        {headline.partial && (
          <span
            className="rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-900"
            title={t("partialHint")}
          >
            {t("partialBadge")}
          </span>
        )}
      </div>
      <p className="mt-4 flex items-start gap-2 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{t("weightsHint", { version })}</span>
      </p>
      <p className="mt-4 leading-7">{report.insights.summary}</p>
      {warnings.map((warning) => (
        <p key={warning} className="mt-3 flex items-start gap-2 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {warning}
        </p>
      ))}
    </section>
  );
}
