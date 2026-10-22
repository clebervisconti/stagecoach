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
        <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <pattern id="ignored-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <path d="M0 0V4" stroke="#F0F0FA" strokeOpacity="0.55" strokeWidth="0.6" />
            </pattern>
          </defs>
          {regions.map((region) => (
            <RegionBox key={region.id} region={region} uncertain={uncertainRole === region.role} />
          ))}
        </svg>
      </div>
      <p id="layout-preview-desc" className="sr-only">
        {description || "No camera or screen regions."}
      </p>
      <figcaption className="mt-2 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
        Frame at {previewT != null ? formatClock(previewT) : "—"} · only you can see this preview
      </figcaption>
    </figure>
  );
}

function RegionBox({ region, uncertain }: { region: LayoutRegion; uncertain: boolean }) {
  const x = region.x * 100;
  const y = region.y * 100;
  const w = region.w * 100;
  const h = region.h * 100;
  const role = region.role === "other_participant" ? "ignore" : region.role;
  const dash = role === "screen" ? "3.5 2" : role === "ignore" ? "0.3 1.8" : undefined;
  const label =
    role === "camera" ? (uncertain ? "CAMERA · CHECK" : "CAMERA") : role === "screen" ? "SCREEN" : "IGNORED";
  return (
    <g>
      {role === "ignore" && <rect x={x} y={y} width={w} height={h} fill="#000" fillOpacity="0.55" />}
      {role === "ignore" && <rect x={x} y={y} width={w} height={h} fill="url(#ignored-hatch)" />}
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        fill="none"
        stroke="#000"
        strokeOpacity="0.6"
        strokeWidth="1.2"
        strokeDasharray={dash}
        vectorEffect="non-scaling-stroke"
      />
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        fill="none"
        stroke="#F0F0FA"
        strokeWidth="0.6"
        strokeDasharray={dash}
        vectorEffect="non-scaling-stroke"
      />
      <foreignObject x={x + 1} y={y + 1} width={Math.max(w - 2, 8)} height="8">
        <div className="inline-flex items-center gap-1 bg-black px-1 py-0.5 font-display text-[10px] uppercase tracking-[0.1em] text-[#F0F0FA] md:text-[11px]">
          {uncertain && <TriangleAlert className="h-3 w-3 text-[color:var(--status-warning)]" aria-hidden="true" />}
          {label}
        </div>
      </foreignObject>
    </g>
  );
}
