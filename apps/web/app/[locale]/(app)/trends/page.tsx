"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { sparklinePath, trendsQuery, type TrendsPayload } from "@/lib/trends";

export default function TrendsPage() {
  const t = useTranslations("trends");
  const [data, setData] = useState<TrendsPayload | null>(null);
  const [error, setError] = useState("");
  const [context, setContext] = useState("");
  const [language, setLanguage] = useState("");
  const [metric, setMetric] = useState("");

  useEffect(() => {
    const url = trendsQuery({
      context: context || undefined,
      language: language || undefined,
      metric: metric || undefined,
    });
    void fetch(url, { cache: "no-store" })
      .then(async (response) => {
        const body = (await response.json()) as TrendsPayload;
        if (!response.ok) throw new Error(t("loadError"));
        setData(body);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [context, language, metric, t]);

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8" data-testid="trends-page">
      <h1 className="mb-2 text-3xl font-bold">{t("heading")}</h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("intro")}</p>
      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        <label className="text-sm font-medium">
          {t("context")}
          <select
            value={context}
            onChange={(event) => setContext(event.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2"
            data-testid="trends-context"
          >
            <option value="">{t("any")}</option>
            <option value="exec_briefing">exec_briefing</option>
            <option value="keynote">keynote</option>
            <option value="sales_pitch">sales_pitch</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          {t("language")}
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2"
          >
            <option value="">{t("any")}</option>
            <option value="en">en</option>
            <option value="pt-BR">pt-BR</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          {t("metric")}
          <select
            value={metric}
            onChange={(event) => setMetric(event.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2"
          >
            <option value="">{t("overall")}</option>
            <option value="pp_wpm">pp_wpm</option>
            <option value="fl_filler_sounds_per_min">fl_filler_sounds_per_min</option>
            <option value="tm_pct_of_slot">tm_pct_of_slot</option>
          </select>
        </label>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {data ? (
        <div className="space-y-6">
          <div data-testid="trends-sparkline" className="rounded-lg border p-4">
            <h2 className="mb-2 text-sm font-semibold">{t("sparkline")}</h2>
            {data.sparkline.length ? (
              <svg viewBox="0 0 120 32" className="h-10 w-40" role="img" aria-label={t("sparkline")}>
                <path d={sparklinePath(data.sparkline)} fill="none" className="stroke-primary" strokeWidth="2" />
              </svg>
            ) : (
              <p className="text-sm text-muted-foreground">{t("empty")}</p>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border p-4" data-testid="trends-improved">
              <h2 className="text-sm font-semibold">{t("mostImproved")}</h2>
              <p className="text-sm text-muted-foreground">
                {data.most_improved
                  ? `${data.most_improved.from} → ${data.most_improved.to}`
                  : t("empty")}
              </p>
            </div>
            <div className="rounded-lg border p-4" data-testid="trends-attention">
              <h2 className="text-sm font-semibold">{t("needsAttention")}</h2>
              <p className="text-sm text-muted-foreground">
                {data.needs_attention
                  ? `${data.needs_attention.from} → ${data.needs_attention.to}`
                  : t("empty")}
              </p>
            </div>
          </div>
          <table className="w-full text-sm" data-testid="trends-table">
            <thead>
              <tr className="border-b text-left">
                <th className="py-2">{t("session")}</th>
                <th className="py-2">{t("value")}</th>
                <th className="py-2">{t("status")}</th>
              </tr>
            </thead>
            <tbody>
              {data.series.map((row) => (
                <tr key={row.session_id} className="border-b last:border-0">
                  <td className="py-2">{row.title || row.session_id}</td>
                  <td className="py-2">{row.value ?? row.overall ?? "—"}</td>
                  <td className="py-2">
                    {row.comparable ? t("comparable") : `${t("notComparable")}: ${row.reason}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
