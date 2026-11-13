"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

type Usage = {
  storage_bytes: number;
  monthly_seconds: number;
  active_jobs: number;
  limits: { storage_bytes: number; monthly_seconds: number; active_jobs: number };
};

type Readiness = {
  self_serve_open: boolean;
  online_modes_enabled: boolean;
  gates: Record<string, string | boolean>;
};

export function AccountUsagePanel() {
  const t = useTranslations("usage");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [ready, setReady] = useState<Readiness | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void Promise.all([
      fetch("/api/stagecoach/account/usage", { cache: "no-store" }).then((response) => response.json()),
      fetch("/api/stagecoach/account/readiness", { cache: "no-store" }).then((response) => response.json()),
    ])
      .then(([usageBody, readyBody]) => {
        setUsage(usageBody);
        setReady(readyBody);
      })
      .catch(() => setError(t("loadError")));
  }, [t]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!usage) return null;
  const storageGb = (usage.storage_bytes / 1024 ** 3).toFixed(2);
  const storageLimit = (usage.limits.storage_bytes / 1024 ** 3).toFixed(0);
  return (
    <div className="rounded-lg border bg-card p-6">
      <h2 className="mb-4 text-lg font-semibold">{t("heading")}</h2>
      <dl className="space-y-2 text-sm">
        <div className="flex justify-between">
          <dt>{t("storage")}</dt>
          <dd>
            {storageGb} / {storageLimit} GB
          </dd>
        </div>
        <div className="flex justify-between">
          <dt>{t("minutes")}</dt>
          <dd>
            {Math.round(usage.monthly_seconds / 60)} / {Math.round(usage.limits.monthly_seconds / 60)}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt>{t("jobs")}</dt>
          <dd>
            {usage.active_jobs} / {usage.limits.active_jobs}
          </dd>
        </div>
      </dl>
      {ready ? (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-medium">{t("readiness")}</h3>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {Object.entries(ready.gates).map(([key, value]) => (
              <li key={key}>
                {key}: {String(value)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
