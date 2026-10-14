"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import type { ConsentItem, ConsentPurpose, ConsentsPayload } from "@/lib/consents";
import { UI_CONSENT_PURPOSES, itemByPurpose } from "@/lib/consents";

type Props = {
  compact?: boolean;
};

export function ConsentPanel({ compact = false }: Props) {
  const t = useTranslations("consents");
  const locale = useLocale();
  const [payload, setPayload] = useState<ConsentsPayload | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<ConsentPurpose | null>(null);

  const load = useCallback(async () => {
    const response = await fetch(`/api/stagecoach/me/consents?locale=${encodeURIComponent(locale)}`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(t("loadError"));
    const body: ConsentsPayload = await response.json();
    setPayload(body);
  }, [locale, t]);

  useEffect(() => {
    const initial = window.setTimeout(() => {
      void load().catch((reason: Error) => setError(reason.message));
    }, 0);
    return () => window.clearTimeout(initial);
  }, [load]);

  async function toggle(purpose: ConsentPurpose, granted: boolean) {
    setPending(purpose);
    setError("");
    try {
      const response = await fetch(`/api/stagecoach/me/consents?locale=${encodeURIComponent(locale)}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ purpose, granted }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || t("saveError"));
      setPayload(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("saveError"));
    } finally {
      setPending(null);
    }
  }

  const videoOn = itemByPurpose(payload, "video_analysis")?.granted === true;

  return (
    <section
      data-testid="consent-panel"
      className={compact ? "md:col-span-2 grid gap-4" : "grid gap-4"}
      aria-labelledby="consent-heading"
    >
      <div>
        <h2 id="consent-heading" className="text-lg font-semibold">
          {t("heading")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("intro")}</p>
        {payload?.policy_version ? (
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {t("policyVersion")}: {payload.policy_version.slice(0, 12)}
          </p>
        ) : null}
      </div>
      {error ? (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          {error}
        </div>
      ) : null}
      {UI_CONSENT_PURPOSES.map((purpose) => {
        const item = itemByPurpose(payload, purpose);
        const locked = purpose !== "video_analysis" && !videoOn;
        return (
          <ConsentCard
            key={purpose}
            purpose={purpose}
            item={item}
            locked={locked}
            busy={pending === purpose}
            onToggle={(granted) => void toggle(purpose, granted)}
          />
        );
      })}
    </section>
  );
}

function ConsentCard({
  purpose,
  item,
  locked,
  busy,
  onToggle,
}: {
  purpose: ConsentPurpose;
  item: ConsentItem | null;
  locked: boolean;
  busy: boolean;
  onToggle: (granted: boolean) => void;
}) {
  const t = useTranslations("consents");
  const granted = item?.granted === true;
  const inputId = `consent-${purpose}`;
  return (
    <article
      data-testid={`consent-${purpose}`}
      className="rounded-lg border bg-card p-4"
    >
      <div className="flex items-start justify-between gap-4">
        <label htmlFor={inputId} className="text-sm font-medium">
          {item?.title ?? purpose}
        </label>
        <input
          id={inputId}
          type="checkbox"
          role="switch"
          aria-checked={granted}
          checked={granted}
          disabled={busy || locked || !item}
          onChange={(event) => onToggle(event.target.checked)}
          className="mt-1 h-4 w-4"
        />
      </div>
      {locked ? <p className="mt-2 text-xs text-muted-foreground">{t("needsVideo")}</p> : null}
      {item ? (
        <dl className="mt-3 grid gap-2 text-sm">
          <div>
            <dt className="font-medium text-muted-foreground">{t("what")}</dt>
            <dd>{item.what}</dd>
          </div>
          <div>
            <dt className="font-medium text-muted-foreground">{t("why")}</dt>
            <dd>{item.why}</dd>
          </div>
          <div>
            <dt className="font-medium text-muted-foreground">{t("limits")}</dt>
            <dd>{item.limits}</dd>
          </div>
          <div>
            <dt className="font-medium text-muted-foreground">{t("never")}</dt>
            <dd>{item.never}</dd>
          </div>
        </dl>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">{t("loading")}</p>
      )}
      {item?.revoked_at && !granted ? (
        <p className="mt-2 text-xs text-muted-foreground">{t("revoked")}</p>
      ) : null}
    </article>
  );
}
