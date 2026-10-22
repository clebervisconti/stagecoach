"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { Info } from "lucide-react";
import { ConfidenceLine } from "@/components/layout/confidence-line";
import { LayoutLegend } from "@/components/layout/layout-legend";
import { LayoutPreview } from "@/components/layout/layout-preview";
import { SegmentStrip } from "@/components/layout/segment-strip";
import { WizardStepper } from "@/components/sessions/new/wizard-stepper";
import { confidenceTone, isDeliveryMode, segmentRoles, type DeliveryMode, type LayoutView } from "@/lib/online";

export default function LayoutReviewPage() {
  const t = useTranslations("online");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const [layout, setLayout] = useState<LayoutView | null>(null);
  const [mode, setMode] = useState<DeliveryMode>("webinar");
  const [selected, setSelected] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.getElementById("layout-title")?.focus();
    document.title = `${t("checkLayout")} · Stage Coach`;
  }, [t]);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const session = await fetch(`/api/stagecoach/sessions/${params.id}`, { cache: "no-store" });
        if (session.ok) {
          const body = (await session.json()) as { delivery_mode?: string };
          if (isDeliveryMode(body.delivery_mode)) setMode(body.delivery_mode);
        }
        const response = await fetch(`/api/stagecoach/sessions/${params.id}/layout`, { cache: "no-store" });
        if (!response.ok) throw new Error(t("layoutLoadError"));
        const body = (await response.json()) as LayoutView;
        if (!active) return;
        setLayout(body);
        setSelected(body.segments[0]?.index ?? 0);
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : t("layoutLoadError"));
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [params.id, t]);

  async function accept(audioOnly: boolean) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/stagecoach/sessions/${params.id}/layout/accept`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ audio_only: audioOnly }),
      });
      if (!response.ok) throw new Error(t("acceptError"));
      router.push(`${prefix}/sessions/${params.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("acceptError"));
      setBusy(false);
    }
  }

  const segment = layout?.segments.find((row) => row.index === selected) ?? layout?.segments[0];
  const tone = layout
    ? confidenceTone(
        layout.confidence,
        layout.review_reason,
        layout.segments.map((row) => row.confidence),
      )
    : "empty";
  const empty = tone === "empty" || (layout && !segment?.regions.length);
  const roles = segmentRoles(segment);
  const preview = segment?.preview_url
    ? `/api/stagecoach${segment.preview_url.replace("/api/v1", "")}`
    : null;

  return (
    <div className="px-5 py-8 md:px-16 md:pt-12">
      <WizardStepper mode={mode} current="layout" />
      <p className="cs-eyebrow">{t("checkLayout")}</p>
      <h1 id="layout-title" tabIndex={-1} className="cs-wizard-title mt-3 max-w-4xl outline-none">
        {t("layoutTitle")}
      </h1>
      <p className="mt-3 max-w-3xl text-base leading-7 text-[color:var(--text-secondary)] md:text-lg md:leading-[30px]">
        {t("layoutLead")}
      </p>

      {loading && (
        <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]" data-testid="layout-loading">
          <div className="aspect-video bg-[color:var(--bg-muted)]" />
          <div className="space-y-4">
            <div className="h-20 bg-[color:var(--bg-muted)]" />
            <div className="h-32 bg-[color:var(--bg-muted)]" />
          </div>
        </div>
      )}

      {!loading && empty && (
        <div className="cs-empty mt-10 rounded-[var(--radius-sm)] border p-10 text-center" data-testid="layout-empty">
          <Info className="relative mx-auto h-6 w-6 text-[color:var(--text-tertiary)]" aria-hidden="true" />
          <p className="relative mt-4 text-sm">{t("noRegions")}</p>
          <button
            type="button"
            data-testid="analyse-audio"
            onClick={() => void accept(true)}
            className="relative mt-6 inline-flex h-11 items-center rounded-[var(--radius-sm)] bg-[color:var(--action-primary)] px-5 text-xs uppercase tracking-[0.08em] text-[color:var(--text-inverse)]"
          >
            {t("analyseAudio")}
          </button>
        </div>
      )}

      {!loading && layout && !empty && (
        <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div>
            <LayoutPreview
              src={preview}
              segment={segment}
              previewT={layout.preview_t}
              uncertainRole={tone === "check" ? "camera" : null}
            />
            <SegmentStrip segments={layout.segments} selected={segment?.index ?? 0} onSelect={setSelected} />
          </div>
          <div className="space-y-8">
            <ConfidenceLine layout={layout} />
            <LayoutLegend roles={roles} />
            <div className="space-y-3">
              <button
                type="button"
                data-testid="looks-right"
                disabled={busy}
                onClick={() => void accept(false)}
                className="inline-flex h-11 w-full items-center justify-center rounded-[var(--radius-sm)] bg-[color:var(--action-primary)] px-5 text-xs uppercase tracking-[0.08em] text-[color:var(--text-inverse)]"
              >
                {t("looksRight")}
              </button>
              <button
                type="button"
                data-testid="analyse-audio"
                disabled={busy}
                onClick={() => void accept(true)}
                className="inline-flex h-11 w-full items-center justify-center rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] px-5 text-xs uppercase tracking-[0.08em]"
              >
                {t("analyseAudio")}
              </button>
              <p className="text-sm text-[color:var(--text-secondary)]">{t("boxesWrong")}</p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div role="alert" className="mt-6 rounded-[var(--radius-sm)] border border-[color:var(--status-critical)] p-4">
          <p className="text-sm text-[color:var(--status-critical)]">{error}</p>
          <button type="button" className="mt-3 text-xs uppercase tracking-[0.08em]" onClick={() => void accept(false)}>
            {t("tryAgain")}
          </button>
        </div>
      )}
    </div>
  );
}
