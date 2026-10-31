"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { normalizeReviewLayout, type ReviewLayout } from "@/lib/review-preference";

export function ReviewPreferencePanel() {
  const t = useTranslations("settings");
  const [visible, setVisible] = useState(false);
  const [value, setValue] = useState<ReviewLayout>("when_unsure");
  const [confirmed, setConfirmed] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/stagecoach/me", { cache: "no-store" });
    if (!response.ok) return;
    const body = await response.json();
    if (!body.online_modes_enabled) {
      setVisible(false);
      return;
    }
    setVisible(true);
    setValue(normalizeReviewLayout(body.review_layout));
    setConfirmed(Number(body.confirmed_online_layouts) || 0);
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  async function choose(next: ReviewLayout) {
    const previous = value;
    setValue(next);
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const response = await fetch("/api/stagecoach/me", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ review_layout: next }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error("save");
      setValue(normalizeReviewLayout(body.review_layout ?? next));
      setSaved(true);
    } catch {
      setValue(previous);
      setError(previous);
    } finally {
      setSaving(false);
    }
  }

  if (!visible) return null;
  const options: ReviewLayout[] = ["always", "when_unsure", "never"];

  return (
    <section data-testid="review-preference" className="rounded-lg border bg-card p-6" aria-labelledby="review-pref-heading">
      <h2 id="review-pref-heading" className="text-lg font-semibold">
        {t("reviewPref.title")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("reviewPref.sub")}</p>
      {error ? (
        <div role="alert" className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          <p>{t("reviewPref.errorTitle")}</p>
          <p>{t("reviewPref.errorBody", { choice: t(`reviewPref.${error}`) })}</p>
        </div>
      ) : null}
      <fieldset className="mt-4 grid gap-3" disabled={saving}>
        <legend>{t("reviewPref.legend")}</legend>
        {options.map((key) => (
          <label key={key} className="flex min-h-11 items-start gap-3 rounded-md border p-3 text-sm">
            <input
              type="radio"
              name="review_layout"
              className="mt-1"
              checked={value === key}
              onChange={() => void choose(key)}
            />
            <span>
              <span className="font-medium">{t(`reviewPref.${key}`)}</span>
              {key === "when_unsure" && (
                <span className="ml-2 rounded-full border px-2 py-0.5 text-xs">{t("reviewPref.default")}</span>
              )}
              <span className="mt-0.5 block text-muted-foreground">{t(`reviewPref.${key}Hint`)}</span>
              {key === "when_unsure" && (
                <span className="mt-1 block font-mono text-xs">
                  {t("reviewPref.meter", { count: Math.min(confirmed, 3) })}
                </span>
              )}
            </span>
          </label>
        ))}
      </fieldset>
      <p className="mt-3 text-sm" role="status">
        {saving ? t("reviewPref.saving") : saved ? t("reviewPref.saved") : ""}
        {saved && value === "never" ? ` ${t("reviewPref.neverNote")}` : ""}
      </p>
    </section>
  );
}
