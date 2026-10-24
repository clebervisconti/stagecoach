"use client";

import { useTranslations } from "next-intl";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { confidenceTone, summariseLayouts, type LayoutComposition, type LayoutView } from "@/lib/online";

export function ConfidenceLine({ layout, consentOff = false }: { layout: LayoutView; consentOff?: boolean }) {
  const t = useTranslations("online");
  const tone = confidenceTone(
    layout.confidence,
    layout.review_reason,
    layout.segments.map((row) => row.confidence),
  );
  const summary = summariseLayouts(layout.segments);
  const word =
    tone === "high" ? t("confidenceHigh") : tone === "unsure" ? t("confidenceUnsure") : t("confidenceCheck");
  const sentence = consentOff
    ? t("layout.consentBody")
    : tone !== "high"
      ? tone === "unsure"
        ? t("unsureLayout")
        : layout.review_reason === "screen_region_unclear"
          ? t("unsureScreen")
          : t("unsureCamera")
      : summary.mixed
        ? `${t("foundDominant", { layout: dominantLayoutLabel(summary.dominant, t) })} ${
            summary.cameraSegments > 0
              ? t("cameraAppears", { n: summary.cameraSegments })
              : t("cameraAppearsNone")
          }`
        : summary.dominant === "camera"
          ? t("foundCamera")
          : summary.dominant === "screen"
            ? t("foundScreen")
            : t("foundBoth");
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
        {consentOff ? t("layout.layoutCheck") : word}
      </p>
      <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{sentence}</p>
    </div>
  );
}

function dominantLayoutLabel(
  dominant: LayoutComposition,
  t: ReturnType<typeof useTranslations<"online">>,
): string {
  if (dominant === "camera") return t("dominantLayout.camera");
  if (dominant === "screen") return t("dominantLayout.screen");
  if (dominant === "audio") return t("dominantLayout.audio");
  return t("dominantLayout.camera_screen");
}
