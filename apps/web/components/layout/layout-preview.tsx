"use client";

import { useTranslations } from "next-intl";
import { TriangleAlert } from "lucide-react";
import { formatClock, regionPositionWords, type LayoutRegion, type LayoutSegment } from "@/lib/online";

export function LayoutPreview({
  src,
  segment,
  previewT,
  uncertainRole,
}: {
  src: string | null;
  segment: LayoutSegment | undefined;
  previewT?: number | null;
  uncertainRole?: string | null;
}) {
  const t = useTranslations("online");
  const regions = segment?.regions ?? [];
  const description = regions
    .map((region) => {
      const { position, size } = regionPositionWords(region);
      const role = region.role === "other_participant" ? t("chip.ignored") : t(`chip.${region.role}`);
      return `${role}: ${position}, ${size}.`;
    })
    .join(" ");

  return (
    <figure>
      <div
        className="relative aspect-video overflow-hidden bg-black"
        tabIndex={0}
        data-testid="layout-preview"
        aria-describedby="layout-preview-desc"
      >
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" className="h-full w-full object-contain" />
        ) : (
          <div className="h-full w-full bg-[color:var(--bg-muted)]" />
        )}
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          {regions.map((region) => (
            <RegionBox key={region.id} region={region} uncertain={uncertainRole === region.role} />
          ))}
        </div>
      </div>
      <p id="layout-preview-desc" className="sr-only">
        {description || t("noRegions")}
      </p>
      <figcaption className="mt-2 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
        {previewT != null ? t("frameAt", { time: formatClock(previewT) }) : t("previewOnly")}
      </figcaption>
    </figure>
  );
}

function RegionBox({ region, uncertain }: { region: LayoutRegion; uncertain: boolean }) {
  const t = useTranslations("online");
  const w = Math.max(region.w, 0.02);
  const h = Math.max(region.h, 0.02);
  const x = region.x;
  const y = region.y;
  const role = region.role === "other_participant" ? "ignore" : region.role;
  const kind = role === "camera" ? "camera" : role === "screen" ? "screen" : "ignored";
  const label = role === "camera" ? t("chip.camera") : role === "screen" ? t("chip.screen") : t("chip.ignored");
  return (
    <div
      className={`cs-region cs-region--${kind}`}
      style={{
        left: `max(1px, ${x * 100}%)`,
        top: `max(1px, ${y * 100}%)`,
        right: `max(1px, ${(1 - x - w) * 100}%)`,
        bottom: `max(1px, ${(1 - y - h) * 100}%)`,
      }}
    >
      <span className="cs-region__label">
        {uncertain && <TriangleAlert className="h-3 w-3 shrink-0 text-[color:var(--status-warning)]" aria-hidden="true" />}
        {label}
        {uncertain && role === "camera" && <span className="cs-region__check"> · {t("confidenceCheck")}</span>}
      </span>
    </div>
  );
}
