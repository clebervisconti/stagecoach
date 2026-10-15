"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  DEFAULT_RETENTION_POLICY,
  RETENTION_POLICIES,
  normalizeRetentionPolicy,
  type RetentionPolicy,
} from "@/lib/retention";

export function RetentionPanel() {
  const t = useTranslations("retention");
  const [policy, setPolicy] = useState<RetentionPolicy>(DEFAULT_RETENTION_POLICY);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch("/api/stagecoach/me", { cache: "no-store" });
    if (!response.ok) throw new Error(t("loadError"));
    const body = await response.json();
    setPolicy(normalizeRetentionPolicy(body.retention_policy));
  }, [t]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void load().catch((reason: Error) => setError(reason.message));
    }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  async function choose(next: RetentionPolicy) {
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/stagecoach/me", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ retention_policy: next }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || t("saveError"));
      setPolicy(normalizeRetentionPolicy(body.retention_policy));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section data-testid="retention-panel" className="rounded-lg border bg-card p-6" aria-labelledby="retention-heading">
      <h2 id="retention-heading" className="text-lg font-semibold">
        {t("heading")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("intro")}</p>
      {error ? (
        <div role="alert" className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          {error}
        </div>
      ) : null}
      <fieldset className="mt-4 grid gap-3" disabled={saving}>
        <legend className="sr-only">{t("heading")}</legend>
        {RETENTION_POLICIES.map((key) => (
          <label key={key} className="flex items-start gap-3 text-sm">
            <input
              type="radio"
              name="retention_policy"
              className="mt-1"
              checked={policy === key}
              onChange={() => void choose(key)}
            />
            <span>
              <span className="font-medium">{t(`keys.${key}`)}</span>
              <span className="mt-0.5 block text-muted-foreground">{t(`hints.${key}`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
    </section>
  );
}
