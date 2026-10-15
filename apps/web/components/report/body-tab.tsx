"use client";

import { useTranslations } from "next-intl";
import { formatTimestamp } from "@/lib/player";
import {
  heatMax,
  spaceCellOpacity,
  spacePeak,
  yawMax,
  type BodyPayload,
} from "@/lib/body-slides";

type BodyTabProps = {
  payload: BodyPayload | null;
  onSeek: (tStart: number) => void;
};

function HeatStrip({
  points,
  duration,
  label,
  empty,
  onSeek,
}: {
  points: Array<{ t: number; value: number | null }>;
  duration: number;
  label: string;
  empty: string;
  onSeek: (t: number) => void;
}) {
  const usable = points.filter((p) => typeof p.value === "number");
  if (!usable.length) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  const peak = heatMax(usable);
  const span = Math.max(duration, usable[usable.length - 1]?.t ?? 1, 1);
  return (
    <svg viewBox="0 0 600 36" role="img" aria-label={label} className="h-9 w-full">
      <title>{label}</title>
      {usable.map((point) => {
        const x = (point.t / span) * 600;
        const w = Math.max(2, (1 / span) * 600);
        const opacity = Math.min(1, ((point.value as number) / peak) * 0.9 + 0.1);
        return (
          <rect
            key={point.t}
            x={x}
            y="4"
            width={w}
            height="28"
            className="fill-primary cursor-pointer"
            opacity={opacity}
            onClick={() => onSeek(point.t)}
          />
        );
      })}
    </svg>
  );
}

export function BodyTab({ payload, onSeek }: BodyTabProps) {
  const t = useTranslations("report");
  if (!payload || !payload.available) {
    return <p className="text-sm text-muted-foreground">{t("bodyUnavailable")}</p>;
  }
  const space = payload.space;
  const peak = spacePeak(space.cells || []);
  const yawPeak = yawMax(payload.yaw_histogram);
  return (
    <div data-testid="body-tab" className="space-y-6">
      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-2 font-medium">{t("gestureHeat")}</h3>
        <HeatStrip
          points={payload.heat}
          duration={payload.duration_s}
          label={t("gestureHeat")}
          empty={t("seriesUnavailable")}
          onSeek={onSeek}
        />
      </section>

      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-2 font-medium">{t("gestureSpace")}</h3>
        {peak <= 0 ? (
          <p className="text-sm text-muted-foreground">{t("seriesUnavailable")}</p>
        ) : (
          <svg viewBox="0 0 160 200" role="img" aria-label={t("gestureSpace")} className="mx-auto h-56">
            <title>{t("gestureSpace")}</title>
            <ellipse cx="80" cy="28" rx="16" ry="18" className="fill-muted-foreground/30" />
            <rect x="62" y="46" width="36" height="70" rx="10" className="fill-muted-foreground/25" />
            {Array.from({ length: space.rows }, (_, row) =>
              Array.from({ length: space.cols }, (_, col) => {
                const count = space.cells[row * space.cols + col] || 0;
                const opacity = spaceCellOpacity(count, peak);
                if (opacity <= 0) return null;
                const x = 10 + col * (140 / space.cols);
                const y = 20 + row * (160 / space.rows);
                return (
                  <rect
                    key={`${row}-${col}`}
                    x={x}
                    y={y}
                    width={140 / space.cols - 1}
                    height={160 / space.rows - 1}
                    className="fill-primary"
                    opacity={opacity}
                  />
                );
              }),
            )}
          </svg>
        )}
      </section>

      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-2 font-medium">{t("bodyEvents")}</h3>
        {payload.events.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("seriesUnavailable")}</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {payload.events.map((event, index) => (
              <li key={`${event.type}-${index}`}>
                <button
                  type="button"
                  className="text-primary underline"
                  onClick={() => onSeek(event.t_start)}
                >
                  ▶ {formatTimestamp(event.t_start)} {event.type.replaceAll("_", " ")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-2 font-medium">{t("sway")}</h3>
          {payload.sway.applicable && payload.sway.value != null ? (
            <p className="text-2xl font-semibold">{payload.sway.value.toFixed(2)}</p>
          ) : (
            <p className="text-sm text-muted-foreground">{t("metricNA")}</p>
          )}
        </section>
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-2 font-medium">{t("audienceFacingBar")}</h3>
          {payload.audience_facing_ratio != null ? (
            <p className="text-2xl font-semibold">{Math.round(payload.audience_facing_ratio * 100)}%</p>
          ) : (
            <p className="text-sm text-muted-foreground">{t("metricNA")}</p>
          )}
        </section>
      </div>

      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-2 font-medium">{t("yawHistogram")}</h3>
        {payload.yaw_histogram.length === 0 || yawPeak <= 0 ? (
          <p className="text-sm text-muted-foreground">{t("seriesUnavailable")}</p>
        ) : (
          <svg viewBox="0 0 600 140" role="img" aria-label={t("yawHistogram")} className="h-36 w-full">
            <title>{t("yawHistogram")}</title>
            {payload.yaw_histogram.map((bin, index) => {
              const w = 600 / payload.yaw_histogram.length;
              const h = (bin.count / yawPeak) * 110;
              return (
                <rect
                  key={bin.center}
                  x={index * w + 2}
                  y={120 - h}
                  width={w - 4}
                  height={h}
                  className="fill-primary"
                />
              );
            })}
          </svg>
        )}
      </section>

      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-2 font-medium">{t("notesDown")}</h3>
        {payload.notes_down.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("seriesUnavailable")}</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {payload.notes_down.map((event, index) => (
              <li key={index}>
                <button type="button" className="text-primary underline" onClick={() => onSeek(event.t_start)}>
                  ▶ {formatTimestamp(event.t_start)}–{formatTimestamp(event.t_end)}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-2 font-medium">
          {t("expressivityLine")} <span className="text-xs text-muted-foreground">{t("optIn")}</span>
        </h3>
        {payload.expressivity.available ? (
          <HeatStrip
            points={payload.expressivity.points}
            duration={payload.duration_s}
            label={t("expressivityLine")}
            empty={t("seriesUnavailable")}
            onSeek={onSeek}
          />
        ) : (
          <p className="text-sm text-muted-foreground">{t("expressivityOff")}</p>
        )}
      </section>

      <section className="rounded-lg border bg-card p-4" data-testid="data-quality">
        <h3 className="mb-2 font-medium">{t("dataQuality")}</h3>
        {!payload.quality ? (
          <p className="text-sm text-muted-foreground">{t("seriesUnavailable")}</p>
        ) : (
          <dl className="grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">{t("personVisible")}</dt>
              <dd>
                {payload.quality.person_visible_ratio != null
                  ? `${Math.round(payload.quality.person_visible_ratio * 100)}%`
                  : t("metricNA")}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("faceVisible")}</dt>
              <dd>
                {payload.quality.face_visible_ratio != null
                  ? `${Math.round(payload.quality.face_visible_ratio * 100)}%`
                  : t("metricNA")}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("facePx")}</dt>
              <dd>
                {payload.quality.mean_face_height_px != null
                  ? `${Math.round(payload.quality.mean_face_height_px)} px`
                  : t("metricNA")}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("personPx")}</dt>
              <dd>
                {payload.quality.mean_person_height_px != null
                  ? `${Math.round(payload.quality.mean_person_height_px)} px`
                  : t("metricNA")}
              </dd>
            </div>
          </dl>
        )}
      </section>
    </div>
  );
}
