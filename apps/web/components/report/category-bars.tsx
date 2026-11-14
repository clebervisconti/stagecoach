"use client";

import { useTranslations } from "next-intl";
import { CATEGORY_IDS, type AnalysisReport } from "@/lib/report-types";
import type { GoalLike } from "@/lib/report-view";

export function CategoryBars({ report, goals = [] }: { report: AnalysisReport; goals?: GoalLike[] }) {
  const t = useTranslations("report");
  const goalByCategory = new Map<string, number>();
  for (const goal of goals) {
    if (goal.category_id && Number.isFinite(goal.target)) goalByCategory.set(goal.category_id, goal.target);
  }
  const rows = [...report.categories].sort((a, b) => {
    const left = a.applicable && a.score !== null ? a.score : -1;
    const right = b.applicable && b.score !== null ? b.score : -1;
    return right - left;
  });
  const label = (id: string) =>
    (CATEGORY_IDS as readonly string[]).includes(id)
      ? t(`categoriesNamed.${id as (typeof CATEGORY_IDS)[number]}`)
      : id.replaceAll("_", " ");
  const summary = rows
    .map((row) => {
      const name = label(row.id);
      return row.applicable && row.score !== null ? `${name} ${Math.round(row.score)}` : `${name} ${t("unavailable")}`;
    })
    .join(", ");

  return (
    <figure className="cs-panel" data-testid="category-bars">
      <figcaption className="cs-panel-title">{t("categories")}</figcaption>
      <div role="img" aria-label={summary} className="grid gap-3">
        {rows.map((row, index) => {
          const scored = row.applicable && row.score !== null;
          const width = scored ? Math.max(0, Math.min(100, row.score ?? 0)) : 0;
          const goal = goalByCategory.get(row.id);
          return (
            <div key={row.id} className={index === 0 && scored ? "s-bar hero" : "s-bar"}>
              <span>{label(row.id)}</span>
              <span className="t" aria-hidden="true">
                {scored ? <i style={{ width: `${width}%` }} /> : null}
                {typeof goal === "number" ? (
                  <i className="goal" data-testid="goal-mark" style={{ left: `${Math.max(0, Math.min(100, goal))}%` }} />
                ) : null}
              </span>
              <span className="v">{scored ? Math.round(row.score ?? 0) : t("unavailable")}</span>
            </div>
          );
        })}
      </div>
    </figure>
  );
}
