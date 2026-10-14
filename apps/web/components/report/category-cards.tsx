"use client";

import { useTranslations } from "next-intl";
import {
  KEY_METRIC_IDS,
  PILLAR_IDS,
  type AnalysisReport,
  type CategoryId,
  type ReportCategory,
} from "@/lib/report-types";

const NAMED_CATEGORIES = new Set<string>([
  "core_message",
  "structure",
  "storytelling",
  "audience_adaptation",
  "opening_close",
  "clarity",
  "impact",
  "visual_aids",
  "pace_pausing",
  "vocal_variety",
  "fluency",
  "gestures_body",
  "eye_contact",
  "facial_affect",
  "energy_presence",
  "time_management",
  "qa",
]);
const ENABLE_HINTS = new Set(["visual_aids", "gestures_body", "eye_contact", "facial_affect", "qa"]);
const KEY_METRIC_SET = new Set<string>(KEY_METRIC_IDS);
import { categoriesByPillar, metricsById } from "@/lib/report-view";
import { MetricInfo } from "./metric-info";

type CategoryCardsProps = {
  report: AnalysisReport;
};

function ConfidenceChip({ label }: { label: ReportCategory["confidence_label"] }) {
  const t = useTranslations("report");
  if (!label) return null;
  const text =
    label === "high" ? t("confidenceHigh") : label === "medium" ? t("confidenceMedium") : t("confidenceLow");
  const hatch = label === "low" ? "bg-[repeating-linear-gradient(45deg,transparent,transparent_4px,rgba(0,0,0,0.08)_4px,rgba(0,0,0,0.08)_8px)]" : "";
  return (
    <span className={`rounded-full bg-muted px-2 py-0.5 text-xs font-medium ${hatch}`}>
      {t("confidence")}: {text}
    </span>
  );
}

function CategoryCard({
  category,
  report,
}: {
  category: ReportCategory;
  report: AnalysisReport;
}) {
  const t = useTranslations("report");
  const metrics = metricsById(report);
  const name = NAMED_CATEGORIES.has(category.id)
    ? t(`categoriesNamed.${category.id as CategoryId}`)
    : category.id.replaceAll("_", " ");
  const version = report.provenance?.scoring_config_version ?? "1.0.0";
  const enable = ENABLE_HINTS.has(category.id)
    ? t(`enableHint.${category.id as "visual_aids" | "gestures_body" | "eye_contact" | "facial_affect" | "qa"}`)
    : null;
  const unavailable = !category.applicable || category.score === null;

  return (
    <article
      className={`rounded-lg border p-5 ${unavailable ? "bg-muted/40 text-muted-foreground" : "bg-card"}`}
      aria-label={name}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="font-semibold text-foreground">{name}</h4>
        {unavailable ? (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">{t("na")}</span>
        ) : (
          <span className="text-2xl font-bold text-foreground">{category.score}</span>
        )}
      </header>
      {!unavailable && (
        <div className="mt-2 flex flex-wrap gap-2">
          {category.level !== null && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-foreground">
              {t("levelChip", { level: category.level })}
              {category.level >= 1 && category.level <= 5
                ? ` · ${t(`level${category.level as 1 | 2 | 3 | 4 | 5}`)}`
                : ""}
            </span>
          )}
          <ConfidenceChip label={category.confidence_label} />
        </div>
      )}
      {unavailable && (
        <div className="mt-3 space-y-2 text-sm">
          <p>{category.na_reason || t("unavailable")}</p>
          {enable && <p>{enable}</p>}
        </div>
      )}
      {!unavailable && (
        <div className="mt-4 space-y-3 text-sm">
          <div>
            <p className="font-medium">{t("whyThisScore")}</p>
            {category.top_contributors.length ? (
              <ul className="mt-2 space-y-2">
                {category.top_contributors.slice(0, 2).map((metricId) => {
                  const metric = metrics.get(metricId);
                  const label = KEY_METRIC_SET.has(metricId)
                    ? t(`keyMetrics.${metricId as (typeof KEY_METRIC_IDS)[number]}`)
                    : metricId.replaceAll("_", " ");
                  const definition = KEY_METRIC_SET.has(metricId)
                    ? t(`keyMetricDefinitions.${metricId as (typeof KEY_METRIC_IDS)[number]}`)
                    : label;
                  const raw =
                    metric && typeof metric.raw_value === "number" ? String(metric.raw_value) : t("unavailable");
                  return (
                    <li key={metricId} className="flex items-start justify-between gap-2 rounded-md bg-muted/50 p-2">
                      <div>
                        <p>{label}</p>
                        <p className="text-xs text-muted-foreground">
                          {t("rawValue")}: {raw}
                          {metric?.target_band ? ` · ${t("targetBand")}: ${metric.target_band}` : ""}
                        </p>
                      </div>
                      <MetricInfo
                        title={label}
                        definition={definition}
                        source={metric?.basis.source ?? null}
                        basisKind={metric?.basis.kind ?? null}
                        confidence={metric?.confidence ?? null}
                        value={typeof metric?.raw_value === "number" ? String(metric.raw_value) : null}
                        targetBand={metric?.target_band}
                      />
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-1 text-muted-foreground">{t("noEvidence")}</p>
            )}
          </div>
          {category.counterfactual && (
            <p>
              <span className="font-medium">{t("counterfactual")}: </span>
              {category.counterfactual}
            </p>
          )}
          <p>
            <span className="font-medium">{t("whatGoodLooksLike")}: </span>
            {t("level5Anchor", { version })}
          </p>
          {category.sources.length > 0 && (
            <p>
              <span className="font-medium">{t("sources")}: </span>
              {category.sources.map((source) => (
                <span
                  key={source}
                  className="mr-1 inline-block rounded bg-muted px-1.5 py-0.5 font-mono text-xs"
                >
                  {source === "heuristic" ? t("heuristic") : source}
                </span>
              ))}
            </p>
          )}
        </div>
      )}
    </article>
  );
}

export function CategoryCards({ report }: CategoryCardsProps) {
  const t = useTranslations("report");
  const grouped = categoriesByPillar(report);

  return (
    <section aria-labelledby="categories-heading">
      <h2 id="categories-heading" className="mb-4 text-2xl font-semibold">
        {t("categories")}
      </h2>
      <div className="space-y-8">
        {PILLAR_IDS.map((pillarId) => {
          const cards = grouped.get(pillarId) ?? [];
          if (!cards.length) return null;
          return (
            <div key={pillarId}>
              <h3 className="mb-3 text-lg font-medium">{t(`pillars.${pillarId}`)}</h3>
              <div className="grid gap-4 md:grid-cols-2">
                {cards.map((category) => (
                  <CategoryCard key={category.id} category={category} report={report} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
