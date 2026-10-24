"use client";

import { useTranslations } from "next-intl";
import type { AnalysisReport, ReportInsight } from "@/lib/report-types";
import { formatTimestamp } from "@/lib/player";
import { evidenceById, isSessionWideEvidence } from "@/lib/report-view";
import { CATEGORY_IDS } from "@/lib/report-types";

type InsightsPanelProps = {
  report: AnalysisReport;
  onSeek?: (tStart: number) => void;
};

function InsightList({
  items,
  empty,
  tone,
  report,
  onSeek,
}: {
  items: ReportInsight[];
  empty: string;
  tone: "opp" | "str" | "weak";
  report: AnalysisReport;
  onSeek?: (tStart: number) => void;
}) {
  const t = useTranslations("report");
  const titleFor = (item: ReportInsight) => {
    const known = (CATEGORY_IDS as readonly string[]).includes(item.category_id);
    const name = known
      ? t(`categoriesNamed.${item.category_id as (typeof CATEGORY_IDS)[number]}`)
      : item.category_id.replaceAll("_", " ");
    if (tone === "str") return t("strengthTitle", { name });
    if (tone === "weak") return t("weaknessTitle", { name });
    if (tone === "opp") return t("opportunityTitle", { name });
    return item.title;
  };
  const toneClass = {
    opp: "bg-[color:var(--bg-subtle)]",
    str: "bg-[color:var(--bg-subtle)]",
    weak: "bg-[color:var(--bg-subtle)]",
  }[tone];
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={`${item.category_id}-${item.title}`} className={`rounded-md p-3 ${toneClass}`}>
          <p className="font-medium">{titleFor(item)}</p>
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
          {item.evidence_ids.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {item.evidence_ids.map((id) => {
                const evidence = evidenceById(report).get(id);
                if (!evidence || evidence.category_id !== item.category_id) return null;
                if (isSessionWideEvidence(evidence)) {
                  return (
                    <span
                      key={id}
                      className="rounded-md border bg-background px-2 py-1 font-mono text-xs text-muted-foreground"
                    >
                      {t("wholeSession")}
                    </span>
                  );
                }
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => onSeek?.(evidence.t_start)}
                    className="rounded-md border bg-background px-2 py-1 font-mono text-xs hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    ▶ {formatTimestamp(evidence.t_start)}
                  </button>
                );
              })}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

export function InsightsPanel({ report, onSeek }: InsightsPanelProps) {
  const t = useTranslations("report");
  const { opportunities, strengths, weaknesses } = report.insights;
  const opportunityIds = new Set(opportunities.slice(0, 3).map((item) => item.category_id));
  const shownStrengths = strengths.filter((item) => !opportunityIds.has(item.category_id));

  return (
    <div className="space-y-6">
      <section className="rounded-lg border bg-card p-6" aria-labelledby="opportunities-heading">
        <h2 id="opportunities-heading" className="text-xl font-semibold">
          {t("opportunities")}
        </h2>
        <div className="mt-4">
          <InsightList items={opportunities.slice(0, 3)} empty={t("noOpportunities")} tone="opp" report={report} onSeek={onSeek} />
        </div>
      </section>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-lg border bg-card p-6" aria-labelledby="strengths-heading">
          <h2 id="strengths-heading" className="text-xl font-semibold">
            {t("strengths")}
          </h2>
          <div className="mt-4">
            <InsightList items={shownStrengths.slice(0, 3)} empty={t("noStrengthsYet")} tone="str" report={report} onSeek={onSeek} />
          </div>
        </section>
        <section className="rounded-lg border bg-card p-6" aria-labelledby="weaknesses-heading">
          <h2 id="weaknesses-heading" className="text-xl font-semibold">
            {t("weaknesses")}
          </h2>
          <div className="mt-4">
            <InsightList items={weaknesses} empty={t("noWeaknesses")} tone="weak" report={report} onSeek={onSeek} />
          </div>
        </section>
      </div>
    </div>
  );
}
