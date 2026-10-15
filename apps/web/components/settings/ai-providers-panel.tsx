"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  DEFAULT_LLM_BASE_URLS,
  LLM_PROVIDERS,
  emptyLlmSettings,
  normalizeLlmSettings,
  type LlmProviderId,
  type LlmSettings,
} from "@/lib/llm-providers";

type CatalogEntry = {
  id: LlmProviderId;
  key_configured: boolean;
  key_envs: string[];
  needs_base_url: boolean;
};

export function AiProvidersPanel() {
  const t = useTranslations("aiProviders");
  const [settings, setSettings] = useState<LlmSettings>(emptyLlmSettings());
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const [me, providers] = await Promise.all([
      fetch("/api/stagecoach/me", { cache: "no-store" }),
      fetch("/api/stagecoach/me/ai-providers", { cache: "no-store" }),
    ]);
    if (!me.ok) throw new Error(t("loadError"));
    const meBody = await me.json();
    setSettings(normalizeLlmSettings(meBody.llm_settings));
    if (providers.ok) {
      const catalogBody = await providers.json();
      setCatalog(catalogBody.providers || []);
    }
  }, [t]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void load().catch((reason: Error) => setError(reason.message));
    }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  async function save(next: LlmSettings) {
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/stagecoach/me", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          llm_settings: {
            provider: next.provider,
            base_url: next.base_url,
            model: next.model,
          },
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || t("saveError"));
      setSettings(normalizeLlmSettings(body.llm_settings));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  function choose(provider: LlmProviderId) {
    const next = normalizeLlmSettings({
      provider,
      base_url: provider === settings.provider ? settings.base_url : DEFAULT_LLM_BASE_URLS[provider],
      model: settings.model,
    });
    void save(next);
  }

  const entry = (id: LlmProviderId) => catalog.find((row) => row.id === id);
  const showUrl = settings.provider === "local" || settings.provider === "custom";

  return (
    <section data-testid="ai-providers-panel" className="rounded-lg border bg-card p-6" aria-labelledby="ai-providers-heading">
      <h2 id="ai-providers-heading" className="text-lg font-semibold">
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
        {LLM_PROVIDERS.map((id) => (
          <label key={id} className="flex items-start gap-3 text-sm">
            <input
              type="radio"
              name="llm_provider"
              className="mt-1"
              checked={settings.provider === id}
              onChange={() => choose(id)}
            />
            <span>
              <span className="font-medium">{t(`keys.${id}`)}</span>
              <span className="mt-0.5 block text-muted-foreground">{t(`hints.${id}`)}</span>
              {entry(id) ? (
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  {entry(id)?.key_configured
                    ? t("keyPresent")
                    : t("keyMissing", { env: (entry(id)?.key_envs || []).join(" / ") })}
                </span>
              ) : null}
            </span>
          </label>
        ))}
      </fieldset>
      {showUrl ? (
        <label className="mt-4 block text-sm">
          <span className="font-medium">{t("baseUrl")}</span>
          <input
            type="url"
            className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2"
            value={settings.base_url}
            disabled={saving}
            onBlur={() => void save(settings)}
            onChange={(event) =>
              setSettings(normalizeLlmSettings({ ...settings, base_url: event.target.value }))
            }
          />
        </label>
      ) : null}
      {settings.leaves_machine ? (
        <div role="alert" data-testid="llm-leaves-machine" className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          {t("leavesMachine")}
        </div>
      ) : null}
    </section>
  );
}
