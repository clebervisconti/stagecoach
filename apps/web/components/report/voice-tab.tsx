"use client";

import { useTranslations } from "next-intl";
import {
  availableSeriesPoints,
  FILLER_REF_HIGH,
  FILLER_REF_LOW,
  fillerRatePerSection,
  paceWindows,
  pauseHistogram,
  wpmBand,
  type SeriesPayload,
} from "@/lib/voice-charts";
import type { TranscriptPayload } from "@/lib/transcript";

type VoiceTabProps = {
  transcript: TranscriptPayload | null;
  contextType?: string;
  pace: SeriesPayload | null;
  pitch: SeriesPayload | null;
  loudness: SeriesPayload | null;
  energy: SeriesPayload | null;
  onSeek: (tStart: number) => void;
};

function LineChart({
  label,
  points,
  onSeek,
  band,
  empty,
}: {
  label: string;
  points: Array<{ t: number; value: number | null }>;
  onSeek: (t: number) => void;
  band?: [number, number];
  empty: string;
}) {
  const usable = points.filter((point) => typeof point.value === "number");
  if (usable.length < 2) {
    return (
      <div>
        <h3 className="mb-2 font-medium">{label}</h3>
        <p className="text-sm text-muted-foreground">{empty}</p>
      </div>
    );
  }
  const maxT = Math.max(...usable.map((point) => point.t), 1);
  const values = usable.map((point) => point.value as number);
  const min = Math.min(...values, band?.[0] ?? values[0]);
  const max = Math.max(...values, band?.[1] ?? values[0]);
  const range = Math.max(max - min, 1);
  const mapped = usable.map((point) => {
    const x = (point.t / maxT) * 600;
    const y = 120 - (((point.value as number) - min) / range) * 100;
    return { ...point, x, y };
  });
  const polyline = mapped.map((point) => `${point.x},${point.y}`).join(" ");
  return (
    <div>
      <h3 className="mb-2 font-medium">{label}</h3>
      <svg viewBox="0 0 600 140" role="img" aria-label={label} className="h-40 w-full">
        <title>{label}</title>
        {band && (
          <rect
            x="0"
            y={120 - ((band[1] - min) / range) * 100}
            width="600"
            height={((band[1] - band[0]) / range) * 100}
            className="fill-emerald-200/40"
          />
        )}
        <line x1="0" y1="120" x2="600" y2="120" className="stroke-border" />
        <polyline points={polyline} fill="none" className="stroke-primary" strokeWidth="2" />
        {mapped.map((point) => (
          <circle
            key={point.t}
            cx={point.x}
            cy={point.y}
            r="4"
            className="fill-primary cursor-pointer"
            tabIndex={0}
            role="button"
            aria-label={`${label} ${point.t}s`}
            onClick={() => onSeek(point.t)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") onSeek(point.t);
            }}
          />
        ))}
      </svg>
    </div>
  );
}

export function VoiceTab({
  transcript,
  contextType,
  pace,
  pitch,
  loudness,
  energy,
  onSeek,
}: VoiceTabProps) {
  const t = useTranslations("report");
  const band = wpmBand(contextType);
  const computedPace = transcript
    ? paceWindows(transcript).map((window) => ({ t: window.t, value: window.wpm }))
    : [];
  const apiPace = availableSeriesPoints(pace).map((point) => ({ t: point.t, value: point.value }));
  const pacePoints = computedPace.some((point) => point.value !== null) ? computedPace : apiPace;
  const pitchPoints = availableSeriesPoints(pitch);
  const loudnessPoints = availableSeriesPoints(loudness);
  const energyPoints = availableSeriesPoints(energy);
  const pauses = transcript ? pauseHistogram(transcript) : [];
  const fillers = transcript ? fillerRatePerSection(transcript) : [];
  const maxFiller = Math.max(FILLER_REF_HIGH, ...fillers.map((item) => item.rate ?? 0), 1);

  return (
    <div className="space-y-8">
      <LineChart label={t("paceGraph")} points={pacePoints} onSeek={onSeek} band={band} empty={t("unavailable")} />
      <p className="text-xs text-muted-foreground">{t("wpmBand", { band: `${band[0]}–${band[1]}` })}</p>
      <LineChart
        label={t("pitchGraph")}
        points={pitchPoints}
        onSeek={onSeek}
        empty={t("seriesUnavailable")}
      />
      <LineChart
        label={t("loudnessGraph")}
        points={loudnessPoints.length ? loudnessPoints : energyPoints}
        onSeek={onSeek}
        empty={t("seriesUnavailable")}
      />
      <section>
        <h3 className="mb-2 font-medium">{t("pauseHistogram")}</h3>
        {pauses.every((bucket) => bucket.count === 0) ? (
          <p className="text-sm text-muted-foreground">{t("unavailable")}</p>
        ) : (
          <ul className="space-y-2">
            {pauses.map((bucket) => (
              <li key={bucket.label} className="flex items-center gap-3 text-sm">
                <span className="w-24 text-muted-foreground">{bucket.label}</span>
                <span
                  className="h-3 rounded bg-primary"
                  style={{ width: `${Math.min(100, bucket.count * 12)}%` }}
                />
                <span>{bucket.count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="mb-2 font-medium">{t("fillerPerSection")}</h3>
        <p className="mb-3 text-xs text-muted-foreground">{t("fillerBenchmarks")}</p>
        {fillers.length ? (
          <svg viewBox={`0 0 ${Math.max(fillers.length * 48, 200)} 160`} className="h-44 w-full" role="img">
            <title>{t("fillerPerSection")}</title>
            <line
              x1="0"
              y1={140 - (FILLER_REF_LOW / maxFiller) * 120}
              x2={fillers.length * 48}
              y2={140 - (FILLER_REF_LOW / maxFiller) * 120}
              className="stroke-emerald-600"
              strokeDasharray="4 3"
            />
            <line
              x1="0"
              y1={140 - (FILLER_REF_HIGH / maxFiller) * 120}
              x2={fillers.length * 48}
              y2={140 - (FILLER_REF_HIGH / maxFiller) * 120}
              className="stroke-red-600"
              strokeDasharray="4 3"
            />
            {fillers.map((item, index) => {
              const height = item.rate === null ? 0 : (item.rate / maxFiller) * 120;
              return (
                <g key={item.id}>
                  <rect
                    x={index * 48 + 12}
                    y={140 - height}
                    width="24"
                    height={height}
                    className={item.rate === null ? "fill-muted" : "fill-primary"}
                  />
                  <text x={index * 48 + 24} y="155" textAnchor="middle" className="fill-muted-foreground text-[10px]">
                    {item.label}
                  </text>
                </g>
              );
            })}
          </svg>
        ) : (
          <p className="text-sm text-muted-foreground">{t("unavailable")}</p>
        )}
      </section>
    </div>
  );
}
