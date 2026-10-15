"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

type CostItem = {
  job_id: string;
  session_id: string;
  status: string;
  title?: string | null;
  total_cost_usd: number;
  total_duration_s: number;
  llm_cost_known: boolean;
  stages: { stage: string; duration_s: number | null; cost_usd: number | null }[];
};

type Payload = {
  items: CostItem[];
  error_tracking: { choice: string; needs_owner_decision: boolean; detail: string };
};

export default function AdminCostsPage() {
  const t = useTranslations("admin");
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const id = window.setTimeout(() => {
      void fetch("/api/stagecoach/admin/analysis-costs", { cache: "no-store" })
        .then(async (response) => {
          const body = await response.json();
          if (!response.ok) throw new Error(body.detail || t("forbidden"));
          setData(body);
        })
        .catch((reason: Error) => setError(reason.message));
    }, 0);
    return () => window.clearTimeout(id);
  }, [t]);

  return (
    <div className="container mx-auto max-w-4xl px-4 py-10" data-testid="admin-costs">
      <h1 className="text-3xl font-semibold">{t("heading")}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t("intro")}</p>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {data?.error_tracking.needs_owner_decision ? (
        <div role="status" className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          {t("sentryPending")} {data.error_tracking.detail}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">{t("sentryNone")}</p>
      )}
      <table className="mt-6 w-full text-sm">
        <caption className="sr-only">{t("heading")}</caption>
        <thead>
          <tr className="border-b text-left">
            <th className="py-2">{t("session")}</th>
            <th className="py-2">{t("status")}</th>
            <th className="py-2">{t("duration")}</th>
            <th className="py-2">{t("cost")}</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items || []).map((item) => (
            <tr key={item.job_id} className="border-b last:border-0">
              <td className="py-2">{item.title || item.session_id}</td>
              <td className="py-2">{item.status}</td>
              <td className="py-2">{item.total_duration_s}</td>
              <td className="py-2">{item.llm_cost_known ? item.total_cost_usd : t("unknown")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
