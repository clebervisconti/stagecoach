"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

type Series = {
  ready: boolean;
  reason?: string | null;
  overall_delta?: number | null;
  deltas?: Record<string, number>;
  takes?: number;
};

export function SeriesPanel({ planId }: { planId: string }) {
  const t = useTranslations("practice");
  const [series, setSeries] = useState<Series | null>(null);

  useEffect(() => {
    void fetch(`/api/stagecoach/talk-plans/${planId}/series`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => setSeries(body))
      .catch(() => setSeries(null));
  }, [planId]);

  if (!series) return null;
  return (
    <section className="mt-8 rounded-lg border p-4" data-testid="talk-series">
      <h2 className="mb-2 text-lg font-semibold">{t("series")}</h2>
      {series.ready ? (
        <p className="text-sm">
          {series.takes} · {series.overall_delta}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">{series.reason || t("seriesEmpty")}</p>
      )}
    </section>
  );
}
