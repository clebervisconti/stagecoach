"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  ACCESSIBILITY_KEYS,
  emptyAccessibilityProfile,
  normalizeAccessibility,
  type AccessibilityKey,
  type AccessibilityProfile,
} from "@/lib/accessibility";

export function AccessibilityPanel() {
  const t = useTranslations("accessibility");
  const [profile, setProfile] = useState<AccessibilityProfile>(emptyAccessibilityProfile());
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch("/api/stagecoach/me", { cache: "no-store" });
    if (!response.ok) throw new Error(t("loadError"));
    const body = await response.json();
    setProfile(normalizeAccessibility(body.accessibility_profile));
  }, [t]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void load().catch((reason: Error) => setError(reason.message));
    }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  async function toggle(key: AccessibilityKey, granted: boolean) {
    setSaving(true);
    setError("");
    const next = { ...profile, [key]: granted };
    if (key === "wheelchair" && granted) next.seated = true;
    try {
      const response = await fetch("/api/stagecoach/me", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ accessibility_profile: next }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || t("saveError"));
      setProfile(normalizeAccessibility(body.accessibility_profile));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section data-testid="accessibility-panel" className="rounded-lg border bg-card p-6" aria-labelledby="accessibility-heading">
      <h2 id="accessibility-heading" className="text-lg font-semibold">
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
        {ACCESSIBILITY_KEYS.map((key) => (
          <label key={key} className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={profile[key]}
              onChange={(event) => void toggle(key, event.target.checked)}
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
