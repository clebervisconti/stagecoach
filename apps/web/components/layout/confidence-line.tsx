import { CircleCheck, TriangleAlert } from "lucide-react";
import { confidenceTone, layoutComposition, type LayoutView } from "@/lib/online";

export function ConfidenceLine({ layout }: { layout: LayoutView }) {
  const segment = layout.segments[0];
  const tone = confidenceTone(
    layout.confidence,
    layout.review_reason,
    layout.segments.map((row) => row.confidence),
  );
  const composition = layoutComposition(segment);
  const word =
    tone === "high" ? "High confidence" : tone === "check" ? "Check this" : tone === "empty" ? "Check this" : "Not sure";
  const sentence =
    tone === "high"
      ? composition === "camera"
        ? "We found your camera. There's no shared screen."
        : composition === "screen"
          ? "We found your screen. Your camera isn't visible."
          : "We found your camera and your screen."
      : tone === "unsure"
        ? "We're not confident about this layout. If it looks wrong, analyse audio only."
        : layout.review_reason === "screen_region_unclear"
          ? "We weren't sure where your screen is."
          : "We weren't sure where your camera is.";
  const Icon = tone === "high" ? CircleCheck : TriangleAlert;
  const color = tone === "high" ? "text-[color:var(--status-success)]" : "text-[color:var(--status-warning)]";
  return (
    <div
      role="status"
      data-testid="confidence-line"
      className="rounded-[var(--radius-sm)] border border-[color:var(--line)] p-4"
      title={`Layout confidence ${layout.confidence.toFixed(2)}`}
    >
      <p className={`flex items-center gap-2 text-xs uppercase tracking-[0.08em] ${color}`}>
        <Icon className="h-4 w-4" aria-hidden="true" />
        {word}
      </p>
      <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{sentence}</p>
    </div>
  );
}
