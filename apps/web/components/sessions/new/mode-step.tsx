"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Info, TriangleAlert } from "lucide-react";
import { DELIVERY_MODES, type DeliveryMode } from "@/lib/online";
import { ModeCard } from "./mode-card";

export function ModeStep({
  value,
  error,
  onChange,
  onContinue,
  onCancel,
}: {
  value: DeliveryMode | null;
  error: string | null;
  onChange: (mode: DeliveryMode) => void;
  onContinue: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("online");
  const groupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const heading = document.getElementById("mode-step-title");
    heading?.focus({ preventScroll: true });
  }, []);

  function move(delta: number) {
    const index = value ? DELIVERY_MODES.indexOf(value) : -1;
    const next = DELIVERY_MODES[(index + delta + DELIVERY_MODES.length) % DELIVERY_MODES.length];
    onChange(next);
    window.setTimeout(() => {
      groupRef.current?.querySelector<HTMLElement>(`[data-testid="mode-${next}"]`)?.focus();
    }, 0);
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <p className="cs-eyebrow">{t("newAnalysis")}</p>
      <h1 id="mode-step-title" tabIndex={-1} className="cs-wizard-title mt-3 outline-none">
        {t("whereTitle")}
      </h1>
      <p className="mt-3 max-w-2xl text-base leading-7 text-[color:var(--text-secondary)] md:text-lg md:leading-[30px]">
        {t("whereLead")}
      </p>

      <div
        ref={groupRef}
        role="radiogroup"
        aria-labelledby="mode-step-title"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? "mode-choose-error" : undefined}
        data-testid="mode-group"
        onKeyDown={(event) => {
          if (event.key === "ArrowRight" || event.key === "ArrowDown") {
            event.preventDefault();
            move(1);
          }
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
            event.preventDefault();
            move(-1);
          }
        }}
        className="mt-8 grid gap-3 md:grid-cols-4 md:gap-4"
      >
        {DELIVERY_MODES.map((mode) => (
          <ModeCard
            key={mode}
            mode={mode}
            title={t(`modes.${mode}.title`)}
            description={t(`modes.${mode}.description`)}
            coach={t(`modes.${mode}.coach`)}
            selected={value === mode}
            tabIndex={value === mode || (value === null && mode === "stage") ? 0 : -1}
            describedBy={`mode-desc-${mode}`}
            onSelect={() => onChange(mode)}
            onActivate={onContinue}
          />
        ))}
      </div>

      {error && (
        <p
          id="mode-choose-error"
          role="alert"
          className="mt-4 flex items-center gap-2 text-sm text-[color:var(--status-warning)]"
        >
          <TriangleAlert className="h-4 w-4" aria-hidden="true" />
          <span>
            <span className="font-medium uppercase tracking-[0.08em]">{t("chooseWord")}</span> {t("chooseWhere")}
          </span>
        </p>
      )}

      <p className="mt-8 flex items-start gap-2 text-sm text-[color:var(--text-secondary)]">
        <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{t("neverJudge")}</span>
      </p>

      <div className="mt-10 flex items-center justify-between gap-3">
        <button
          type="button"
          data-testid="cancel-mode"
          onClick={onCancel}
          className="inline-flex h-11 items-center rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] px-5 text-xs uppercase tracking-[0.08em]"
        >
          {t("cancel")}
        </button>
        <button
          type="button"
          data-testid="continue-mode"
          onClick={onContinue}
          className="inline-flex h-11 items-center rounded-[var(--radius-sm)] bg-[color:var(--action-primary)] px-5 text-xs uppercase tracking-[0.08em] text-[color:var(--text-inverse)]"
        >
          {t("continue")}
        </button>
      </div>
    </div>
  );
}
