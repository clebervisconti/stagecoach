"use client";

import { useTranslations } from "next-intl";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { confidenceTone, layoutComposition, type LayoutView } from "@/lib/online";

export function ConfidenceLine({ layout }: { layout: LayoutView }) {
  const t = useTranslations("online");
  const segment = layout.segments[0];
  const tone = confidenceTone(
    layout.confidence,
    layout.review_reason,
    layout.segments.map((row) => row.confidence),
  );
  const composition = layoutComposition(segment);
  const word =
    tone === "high" ? t("confidenceHigh") : tone === "unsure" ? t("confidenceUnsure") : t("confidenceCheck");
  const sentence =
    tone === "high"
      ? composition === "camera"
        ? t("foundCamera")
        : composition === "screen"
          ? t("foundScreen")
          : t("foundBoth")
      : tone === "unsure"
        ? t("unsureLayout")
        : layout.review_reason === "screen_region_unclear"
          ? t("unsureScreen")
          : t("unsureCamera");
  const Icon = tone === "high" ? CircleCheck : TriangleAlert;
  const color = tone === "high" ? "text-[color:var(--status-success)]" : "text-[color:var(--status-warning)]";
  return (
    <div
      role="status"
      data-testid="confidence-line"
      className="rounded-[var(--radius-sm)] border border-[color:var(--line)] p-4"
    >
      <p className={`flex items-center gap-2 text-xs uppercase tracking-[0.08em] ${color}`}>
        <Icon className="h-4 w-4" aria-hidden="true" />
        {word}
      </p>
      <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{sentence}</p>
    </div>
  );
}
