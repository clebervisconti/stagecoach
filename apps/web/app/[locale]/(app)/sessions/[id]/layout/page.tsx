"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { LayoutWorkspace, type LayoutHeading } from "@/components/layout/layout-workspace";
import { WizardStepper } from "@/components/sessions/new/wizard-stepper";
import type { LayoutDraft } from "@/lib/layout-edit";
import { isDeliveryMode, type DeliveryMode, type LayoutView } from "@/lib/online";

let layoutLoadGeneration = 0;

export default function LayoutReviewPage() {
  const t = useTranslations("online");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const sessionHref = `${prefix}/sessions/${params.id}`;
  const layoutHref = `${prefix}/sessions/${params.id}/layout`;
  const [layout, setLayout] = useState<LayoutView | null>(null);
  const [mode, setMode] = useState<DeliveryMode>("webinar");
  const [sessionStatus, setSessionStatus] = useState("layout_review");
  const [consentOff, setConsentOff] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [editing, setEditing] = useState(false);
  const [f6, setF6] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const [heading, setHeading] = useState<LayoutHeading>({
    eyebrow: t("checkLayout"),
    title: t("layoutTitle"),
    lead: t("layoutLead"),
  });
  const lastAudioOnly = useRef(false);
  const appliedLayout = useRef(false);
  const onHeading = useCallback((next: LayoutHeading) => {
    setHeading((prev) =>
      prev.eyebrow === next.eyebrow && prev.title === next.title && prev.lead === next.lead ? prev : next,
    );
  }, []);

  useEffect(() => {
    document.getElementById("layout-title")?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    document.title = `${heading.title} · Stage Coach`;
  }, [heading.title]);

  useEffect(() => {
    const generation = ++layoutLoadGeneration;
    let active = true;
    async function load() {
      const query = new URLSearchParams(window.location.search);
      const wantEdit = query.get("edit") === "1";
      const wantF6 = query.get("f6") === "1";
      try {
        const session = await fetch(`/api/stagecoach/sessions/${params.id}`, { cache: "no-store" });
        let status = "layout_review";
        if (session.ok) {
          const body = (await session.json()) as {
            delivery_mode?: string;
            status?: string;
            consent?: { video_analysis?: boolean };
          };
          if (isDeliveryMode(body.delivery_mode)) setMode(body.delivery_mode);
          if (body.status) {
            status = body.status;
            setSessionStatus(body.status);
          }
          setConsentOff(body.consent?.video_analysis === false);
        }
        if (!active || generation !== layoutLoadGeneration) return;
        const reopen = wantF6 && status !== "layout_review" && status !== "preparing" && status !== "created";
        if (reopen) {
          const created = await fetch(`/api/stagecoach/sessions/${params.id}/reanalyse-layout`, { method: "POST" });
          if (!created.ok) throw new Error(t("layout.saveFailedBody"));
          if (active) {
            setF6(true);
            setEditing(true);
            window.history.replaceState(null, "", `${layoutHref}?edit=1`);
          }
        } else if (active) {
          if (wantF6) setF6(true);
          setEditing(wantEdit || wantF6);
        }
        const response = await fetch(`/api/stagecoach/sessions/${params.id}/layout`, { cache: "no-store" });
        if (!response.ok) throw new Error(t("layoutLoadError"));
        const body = (await response.json()) as LayoutView;
        if (!active || appliedLayout.current) return;
        appliedLayout.current = true;
        setLayout(body);
        setResetToken((value) => value + 1);
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
  }, [params.id, t, layoutHref]);

  function enterEdit(next: boolean) {
    setEditing(next);
    const url = next ? `${layoutHref}?edit=1` : layoutHref;
    window.history.replaceState(null, "", url);
  }

  async function accept(audioOnly: boolean) {
    lastAudioOnly.current = audioOnly;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/stagecoach/sessions/${params.id}/layout/accept`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ audio_only: audioOnly }),
      });
      if (!response.ok) throw new Error(t("acceptError"));
      router.push(sessionHref);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("acceptError"));
      setBusy(false);
    }
  }

  async function save(draft: LayoutDraft) {
    if (!layout) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/stagecoach/sessions/${params.id}/layout`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          version: layout.version,
          analysis_window: draft.analysis_window,
          segments: draft.segments.map((segment) => ({
            index: segment.index,
            t_start: segment.t_start,
            t_end: segment.t_end,
            kind: segment.kind,
            confidence: segment.confidence,
            regions: segment.regions.map((region) => ({
              id: region.id,
              role: region.role,
              x: region.x,
              y: region.y,
              w: region.w,
              h: region.h,
              confidence: region.confidence,
              source: region.source ?? "user",
            })),
          })),
        }),
      });
      if (!response.ok) throw new Error(t("layout.saveFailedBody"));
      router.push(sessionHref);
    } catch (reason) {
      setSaveError(true);
      setError(reason instanceof Error ? reason.message : t("layout.saveFailedBody"));
      setBusy(false);
    }
  }

  async function discard() {
    setBusy(true);
    setSaveError(false);
    setError(null);
    try {
      const response = await fetch(`/api/stagecoach/sessions/${params.id}/layout`, { cache: "no-store" });
      if (!response.ok) throw new Error(t("layoutLoadError"));
      setLayout((await response.json()) as LayoutView);
      setResetToken((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("layoutLoadError"));
    } finally {
      setBusy(false);
    }
  }

  const reviewing = sessionStatus === "layout_review" || sessionStatus === "preparing" || sessionStatus === "created";
  const readOnly = Boolean(layout?.auto_confirmed || (layout && !reviewing && !f6 && !editing));
  const auto = Boolean(layout?.auto_confirmed);

  return (
    <div className="px-5 py-8 md:px-16 md:pt-12">
      <WizardStepper
        mode={mode}
        current="layout"
        layoutDone={readOnly || auto}
        autoConfirmed={auto}
        consentOff={consentOff}
        onSelect={(id) => {
          if (id === "where") router.push(`${prefix}/sessions/new?step=where&mode=${mode}`);
          if (id === "recording") router.push(`${prefix}/sessions/new?step=recording&mode=${mode}`);
          if (id === "layout") router.push(layoutHref);
        }}
      />
      <p className="cs-eyebrow">{heading.eyebrow}</p>
      <h1 id="layout-title" tabIndex={-1} className="cs-wizard-title mt-3 max-w-4xl text-balance outline-none">
        {heading.title}
      </h1>
      <p className="mt-3 max-w-3xl text-base leading-7 text-[color:var(--text-secondary)] md:text-lg md:leading-[30px]">
        {heading.lead}
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

      {!loading && layout && (
        <LayoutWorkspace
          key={resetToken}
          layout={layout}
          editing={editing && !readOnly}
          f6={f6}
          consentOff={consentOff}
          readOnly={readOnly}
          auto={auto}
          busy={busy}
          saveError={saveError}
          sessionHref={sessionHref}
          onHeading={onHeading}
          onEditing={enterEdit}
          onAccept={(audioOnly) => void accept(audioOnly)}
          onSave={(draft) => void save(draft)}
          onDiscard={() => void discard()}
        />
      )}

      {error && !saveError && (
        <div role="alert" className="mt-6 rounded-[var(--radius-sm)] border border-[color:var(--status-critical)] p-4">
          <p className="text-sm">
            <span className="font-display text-xs font-bold uppercase tracking-[0.08em] text-[color:var(--status-critical)]">
              {t("acceptErrorWord")}
            </span>
            <span className="text-[color:var(--text)]"> · {error}</span>
          </p>
          <button
            type="button"
            className="mt-3 text-xs uppercase tracking-[0.08em]"
            onClick={() => void accept(lastAudioOnly.current)}
          >
            {t("tryAgain")}
          </button>
        </div>
      )}
    </div>
  );
}
