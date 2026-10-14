"use client";

import { useId, useState } from "react";
import { useTranslations } from "next-intl";
import { Info, X } from "lucide-react";

type MetricInfoProps = {
  title: string;
  definition: string;
  source: string | null;
  basisKind: string | null;
  confidence: number | null;
  value: string | null;
  targetBand?: string | null;
};

export function MetricInfo({
  title,
  definition,
  source,
  basisKind,
  confidence,
  value,
  targetBand,
}: MetricInfoProps) {
  const t = useTranslations("report");
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const sourceLabel =
    basisKind === "heuristic" || source === "heuristic" || source === "H"
      ? t("heuristic")
      : source;

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((valueOpen) => !valueOpen)}
      >
        <Info className="h-4 w-4" aria-hidden="true" />
        <span className="sr-only">{t("metricInfo")}: {title}</span>
      </button>
      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label={title}
          className="absolute right-0 top-7 z-20 w-72 rounded-md border bg-popover p-3 text-left text-sm shadow-md"
        >
          <div className="mb-2 flex items-start justify-between gap-2">
            <p className="font-medium">{title}</p>
            <button
              type="button"
              className="rounded-sm p-1 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => setOpen(false)}
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="sr-only">{t("closeInfo")}</span>
            </button>
          </div>
          <p className="text-muted-foreground">{definition}</p>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted-foreground">{t("rawValue")}</dt>
            <dd>{value ?? t("unavailable")}</dd>
            <dt className="text-muted-foreground">{t("sourceLabel")}</dt>
            <dd>{sourceLabel ?? t("heuristic")}</dd>
            <dt className="text-muted-foreground">{t("confidence")}</dt>
            <dd>
              {confidence === null ? t("unavailable") : `${Math.round(confidence * 100)}%`}
            </dd>
            {targetBand ? (
              <>
                <dt className="text-muted-foreground">{t("targetBand")}</dt>
                <dd>{targetBand}</dd>
              </>
            ) : null}
          </dl>
        </div>
      )}
    </span>
  );
}
