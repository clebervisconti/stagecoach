"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { EDITOR_SECTIONS, downloadMarkdown, sectionText, type PlanRecord } from "@/lib/plan-export";
import { readinessRows, topChanges } from "@/lib/plan-readiness";

type Props = { planId: string };

export function PlanEditor({ planId }: Props) {
  const t = useTranslations("planEditor");
  const locale = useLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const [plan, setPlan] = useState<PlanRecord | null>(null);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(`/api/stagecoach/plans/${planId}`, { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || t("loadError"));
        if (active) setPlan(body);
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message);
      });
    return () => {
      active = false;
    };
  }, [planId, t]);

  async function saveSection(section: string) {
    if (!plan) return;
    setBusy(section);
    setError("");
    try {
      const outputs = { ...(plan.outputs || {}), [section]: drafts[section] ?? sectionText(plan, section as never) };
      const response = await fetch(`/api/stagecoach/plans/${planId}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ outputs }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || t("saveError"));
      setPlan(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("saveError"));
    } finally {
      setBusy("");
    }
  }

  async function regenerate(section: string) {
    setBusy(section);
    setError("");
    try {
      const response = await fetch(`/api/stagecoach/plans/${planId}/regenerate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ section, feedback: feedback[section] || "" }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || t("regenError"));
      setPlan(body);
      setDrafts((prev) => ({
        ...prev,
        [section]: sectionText(body, section as (typeof EDITOR_SECTIONS)[number]),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("regenError"));
    } finally {
      setBusy("");
    }
  }

  function exportMarkdown() {
    if (!plan) return;
    const file = downloadMarkdown(plan);
    const blob = new Blob([file.body], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = file.filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (!plan) {
    return <p className="text-sm text-muted-foreground">{error || t("loading")}</p>;
  }

  const audience = plan.audience || {};

  return (
    <div className="space-y-8" data-testid="plan-editor">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold">{plan.title || t("untitled")}</h1>
        <p className="text-sm text-muted-foreground">
          {plan.context_type} · {String(audience.roles || t("audienceUnset"))} · {plan.slot_min ?? "?"} min
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <button type="button" data-testid="export-markdown" onClick={exportMarkdown} className="rounded-md border px-3 py-1 text-sm">
            {t("exportMarkdown")}
          </button>
          <Link
            href={`${prefix}/prep/${planId}/print`}
            data-testid="export-pdf"
            className="rounded-md border px-3 py-1 text-sm"
          >
            {t("exportPdf")}
          </Link>
        </div>
      </header>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {EDITOR_SECTIONS.map((section) => (
        <section key={section} className="rounded-lg border p-4" data-testid={`section-${section}`}>
          <h2 className="mb-2 font-semibold">{t(`sections.${section}`)}</h2>
          <textarea
            className="w-full rounded-md border px-3 py-2 text-sm"
            rows={5}
            value={drafts[section] ?? sectionText(plan, section)}
            onChange={(event) => setDrafts((prev) => ({ ...prev, [section]: event.target.value }))}
          />
          <label className="mt-2 block text-sm">
            {t("feedback")}
            <input
              className="mt-1 w-full rounded-md border px-3 py-2"
              value={feedback[section] || ""}
              onChange={(event) => setFeedback((prev) => ({ ...prev, [section]: event.target.value }))}
            />
          </label>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={busy === section}
              onClick={() => void saveSection(section)}
              className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground"
            >
              {t("save")}
            </button>
            <button
              type="button"
              data-testid={`regen-${section}`}
              disabled={busy === section}
              onClick={() => void regenerate(section)}
              className="rounded-md border px-3 py-1 text-sm"
            >
              {t("regenerate")}
            </button>
          </div>
        </section>
      ))}

      <section className="rounded-lg border p-4" data-testid="readiness">
        <h2 className="mb-2 font-semibold">{t("readiness")}</h2>
        <ul className="space-y-1 text-sm">
          {readinessRows(plan).map((row) => (
            <li key={row.id}>
              {row.id}: {row.applicable ? (row.ready ? t("ready") : t("needsWork")) : row.na_reason}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border p-4" data-testid="top-changes">
        <h2 className="mb-2 font-semibold">{t("topChanges")}</h2>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          {topChanges(plan).map((row) => (
            <li key={row.id}>
              {row.change} — {row.rewrite}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
