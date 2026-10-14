"use client";

import { useTranslations } from "next-intl";
import type { AnalysisReport } from "@/lib/report-types";
import { keyMetricRows } from "@/lib/report-view";
import { MetricInfo } from "./metric-info";

const LIGHT_CLASS = {
  green: "bg-emerald-100 text-emerald-900",
  yellow: "bg-amber-100 text-amber-900",
  red: "bg-red-100 text-red-900",
} as const;

type KeyMetricsProps = {
  report: AnalysisReport;
};

export function KeyMetrics({ report }: KeyMetricsProps) {
  const t = useTranslations("report");
  const rows = keyMetricRows(report);

  return (
    <section aria-labelledby="key-metrics-heading">
      <h2 id="key-metrics-heading" className="mb-4 text-2xl font-semibold">
        {t("metrics")}
      </h2>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((row) => {
          const title = t(`keyMetrics.${row.id}`);
          return (
            <li key={row.id} className="rounded-lg border bg-card p-5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm text-muted-foreground">{title}</p>
                <MetricInfo
                  title={title}
                  definition={t(`keyMetricDefinitions.${row.id}`)}
                  source={row.source}
                  basisKind={row.basisKind}
                  confidence={row.confidence}
                  value={row.available ? row.formatted : null}
                />
              </div>
              {row.available ? (
                <p className="mt-2 text-3xl font-bold">
                  {row.formatted}{" "}
                  <span className="text-sm font-normal text-muted-foreground">
                    {t(`keyMetricUnits.${row.id}`)}
                  </span>
                </p>
              ) : (
                <p className="mt-2 text-2xl font-semibold text-muted-foreground">{t("unavailable")}</p>
              )}
              {row.light && (
                <p className={`mt-3 inline-block rounded-full px-2 py-0.5 text-xs ${LIGHT_CLASS[row.light]}`}>
                  {t("slotVsActual")}
                </p>
              )}
              {row.id === "fl_filler_sounds_per_min" && row.available && (
                <p className="mt-2 text-xs text-muted-foreground">{t("fillerBenchmarks")}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
