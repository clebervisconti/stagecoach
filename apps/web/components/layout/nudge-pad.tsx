"use client";

import { useTranslations } from "next-intl";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";

export function NudgePad({
  fine,
  onFine,
  onNudge,
}: {
  fine: boolean;
  onFine: (fine: boolean) => void;
  onNudge: (dx: number, dy: number) => void;
}) {
  const t = useTranslations("online");
  const step = fine ? 10 : 1;
  const cell =
    "inline-flex h-11 w-11 items-center justify-center border border-[color:var(--line-strong)] bg-[color:var(--bg)]";
  return (
    <div data-testid="nudge-pad">
      <div className="grid w-[140px] grid-cols-3 gap-1">
        <span />
        <button type="button" className={cell} aria-label={t("layout.nudge.up")} data-testid="nudge-up" onClick={() => onNudge(0, -step)}>
          <ChevronUp className="h-4 w-4" aria-hidden="true" />
        </button>
        <span />
        <button type="button" className={cell} aria-label={t("layout.nudge.left")} data-testid="nudge-left" onClick={() => onNudge(-step, 0)}>
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          className={cell}
          aria-pressed={fine}
          data-testid="nudge-fine"
          aria-label={t("layout.nudge.fine")}
          onClick={() => onFine(!fine)}
        >
          <span className="font-mono text-[10px]">{fine ? "10" : "1"}</span>
        </button>
        <button type="button" className={cell} aria-label={t("layout.nudge.right")} data-testid="nudge-right" onClick={() => onNudge(step, 0)}>
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
        <span />
        <button type="button" className={cell} aria-label={t("layout.nudge.down")} data-testid="nudge-down" onClick={() => onNudge(0, step)}>
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        </button>
        <span />
      </div>
      <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">{t("layout.nudge.hint")}</p>
    </div>
  );
}
