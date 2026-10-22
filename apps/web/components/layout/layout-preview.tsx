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
  const regions = segment?.regions ?? [];
  const description = regions
    .map((region) => {
      const { position, size } = regionPositionWords(region);
      const role = region.role === "other_participant" ? "Ignored" : region.role;
      return `${role}: ${position}, ${size}.`;
    })
    .join(" ");

  return (
    <figure>
      <div className="relative aspect-video overflow-hidden bg-black" tabIndex={0} aria-describedby="layout-preview-desc">
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
        {description || "No camera or screen regions."}
      </p>
      <figcaption className="mt-2 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
        {previewT != null ? `Frame at ${formatClock(previewT)} · only you can see this preview` : "Only you can see this preview"}
      </figcaption>
    </figure>
  );
}

function inset(value: number, size: number): number {
  const min = 0.001;
  const max = 0.999 - size;
  return Math.min(Math.max(value, min), Math.max(min, max));
}

function RegionBox({ region, uncertain }: { region: LayoutRegion; uncertain: boolean }) {
  const w = Math.max(region.w, 0.02);
  const h = Math.max(region.h, 0.02);
  const x = inset(region.x, w);
  const y = inset(region.y, h);
  const role = region.role === "other_participant" ? "ignore" : region.role;
  const kind = role === "camera" ? "camera" : role === "screen" ? "screen" : "ignored";
  const label =
    role === "camera" ? (uncertain ? "Camera · Check" : "Camera") : role === "screen" ? "Screen" : "Ignored";
  return (
    <div
      className={`cs-region cs-region--${kind}`}
      style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` }}
    >
      <span className="cs-region__label">
        {uncertain && <TriangleAlert className="h-3 w-3 text-[color:var(--status-warning)]" aria-hidden="true" />}
        {label}
      </span>
    </div>
  );
}
