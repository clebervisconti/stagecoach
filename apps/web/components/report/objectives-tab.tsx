"use client";

import { useTranslations } from "next-intl";

export type CoachingPayload = {
  objectives: Array<{ id?: string; text?: string; check_type?: string }>;
  planned_vs_actual: Array<{
    section: string;
    planned_min: number | null;
    actual_min: number | null;
    note?: string;
  }>;
  rehearsal_progress: {
    ready: boolean;
    reason?: string;
    rehearsal_count?: number;
    objectives: Array<{ objective_id: string; history: Array<{ status: string; score: number | null }> }>;
  };
  baseline: {
    ready: boolean;
    n_sessions?: number;
    reason?: string;
  };
  badges: Array<{
    metric_id: string;
    z: number | null;
    population_score: number | null;
    kept_score: number | null;
    n: number;
  }>;
};

function minutes(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(1);
}

export function ObjectivesTab({ payload }: { payload: CoachingPayload | null }) {
  const t = useTranslations("report");
  if (!payload) {
    return <p className="text-sm text-muted-foreground">{t("objectivesEmpty")}</p>;
  }
  return (
    <div data-testid="objectives-tab" className="space-y-6">
      <section>
        <h2 className="mb-2 text-lg font-semibold">{t("objectivesTab")}</h2>
        {payload.objectives.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("objectivesEmpty")}</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {payload.objectives.map((item) => (
              <li key={item.id || item.text} className="rounded-md border px-3 py-2">
                <span className="font-medium">{item.text}</span>
                {item.check_type ? (
                  <span className="ml-2 text-muted-foreground">{item.check_type}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">{t("plannedVsActual")}</h2>
        {payload.planned_vs_actual.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("plannedEmpty")}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="py-1 text-left">{t("section")}</th>
                <th className="py-1 text-left">{t("planned")}</th>
                <th className="py-1 text-left">{t("actual")}</th>
              </tr>
            </thead>
            <tbody>
              {payload.planned_vs_actual.map((row) => (
                <tr key={row.section}>
                  <td className="py-1">{row.section}</td>
                  <td className="py-1">{minutes(row.planned_min)}</td>
                  <td className="py-1">{row.actual_min == null ? t("actualPending") : minutes(row.actual_min)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">{t("rehearsalProgress")}</h2>
        {payload.rehearsal_progress.ready ? (
          <ul className="space-y-1 text-sm">
            {payload.rehearsal_progress.objectives.map((item) => (
              <li key={item.objective_id}>
                {item.objective_id}: {item.history.map((step) => step.status).join(" → ")}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            {payload.rehearsal_progress.reason || t("rehearsalWaiting")}
          </p>
        )}
      </section>
      <section data-testid="baseline-panel">
        <h2 className="mb-2 text-lg font-semibold">{t("baselineTitle")}</h2>
        {payload.baseline.ready ? (
          <ul className="space-y-1 text-sm">
            {payload.badges.map((badge) => (
              <li key={badge.metric_id} data-testid="baseline-badge">
                {badge.metric_id}: z={badge.z == null ? t("na") : badge.z.toFixed(2)} · {t("populationScore")}{" "}
                {badge.kept_score ?? badge.population_score ?? t("na")}
              </li>
            ))}
            {payload.badges.length === 0 ? (
              <li className="text-muted-foreground">{t("baselineNoOverlap")}</li>
            ) : null}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            {payload.baseline.reason || t("baselinePending")} ({payload.baseline.n_sessions ?? 0}/3)
          </p>
        )}
      </section>
    </div>
  );
}
