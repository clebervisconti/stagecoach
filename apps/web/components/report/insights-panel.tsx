"use client";

import { useTranslations } from "next-intl";
import type { AnalysisReport, ReportInsight } from "@/lib/report-types";

type InsightsPanelProps = {
  report: AnalysisReport;
};

function InsightList({
  items,
  empty,
  tone,
}: {
  items: ReportInsight[];
  empty: string;
  tone: "opp" | "str" | "weak";
}) {
  const t = useTranslations("report");
  const toneClass = {
    opp: "bg-primary/10",
    str: "bg-emerald-500/10",
    weak: "bg-amber-500/10",
  }[tone];
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={`${item.category_id}-${item.title}`} className={`rounded-md p-3 ${toneClass}`}>
          <p className="font-medium">{item.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{item.body}</p>
          {item.fix && (
            <p className="mt-2 text-sm">
              <span className="font-medium">{t("fix")}: </span>
              {item.fix}
            </p>
          )}
          {item.drill_ids.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("drill")}: {item.drill_ids.join(", ")}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

export function InsightsPanel({ report }: InsightsPanelProps) {
  const t = useTranslations("report");
  const { opportunities, strengths, weaknesses } = report.insights;

  return (
    <div className="space-y-6">
      <section className="rounded-lg border bg-card p-6" aria-labelledby="opportunities-heading">
        <h2 id="opportunities-heading" className="text-xl font-semibold">
          {t("opportunities")}
        </h2>
        <div className="mt-4">
          <InsightList items={opportunities.slice(0, 3)} empty={t("noOpportunities")} tone="opp" />
        </div>
      </section>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-lg border bg-card p-6" aria-labelledby="strengths-heading">
          <h2 id="strengths-heading" className="text-xl font-semibold">
            {t("strengths")}
          </h2>
          <div className="mt-4">
            <InsightList items={strengths.slice(0, 3)} empty={t("noStrengthsYet")} tone="str" />
          </div>
        </section>
        <section className="rounded-lg border bg-card p-6" aria-labelledby="weaknesses-heading">
          <h2 id="weaknesses-heading" className="text-xl font-semibold">
            {t("weaknesses")}
          </h2>
          <div className="mt-4">
            <InsightList items={weaknesses} empty={t("noWeaknesses")} tone="weak" />
          </div>
        </section>
      </div>
    </div>
  );
}
