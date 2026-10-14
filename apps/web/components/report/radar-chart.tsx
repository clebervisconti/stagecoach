"use client";

import { useTranslations } from "next-intl";
import type { PillarId } from "@/lib/report-types";
import { radarAxisPoint, radarPolygon, type RadarPoint } from "@/lib/report-view";

const SIZE = 280;
const CX = 140;
const CY = 140;
const RADIUS = 96;

type RadarChartProps = {
  points: RadarPoint[];
};

export function RadarChart({ points }: RadarChartProps) {
  const t = useTranslations("report");
  const polygon = radarPolygon(points, RADIUS, CX, CY);
  const rings = [0.25, 0.5, 0.75, 1];

  return (
    <figure className="space-y-4">
      <figcaption className="text-sm font-medium">{t("radarCaption")}</figcaption>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-hidden="true"
        className="mx-auto h-64 w-64"
      >
        {rings.map((ring) => {
          const ringPoints = points
            .map((_, index) => radarAxisPoint(index, points.length, RADIUS * ring, CX, CY))
            .map((point) => `${point.x},${point.y}`)
            .join(" ");
          return (
            <polygon
              key={ring}
              points={ringPoints}
              fill="none"
              className="stroke-border"
              strokeWidth="1"
            />
          );
        })}
        {points.map((point, index) => {
          const end = radarAxisPoint(index, points.length, RADIUS, CX, CY);
          const label = radarAxisPoint(index, points.length, RADIUS + 22, CX, CY);
          return (
            <g key={point.id}>
              <line
                x1={CX}
                y1={CY}
                x2={end.x}
                y2={end.y}
                className={point.available ? "stroke-border" : "stroke-muted-foreground/40"}
                strokeDasharray={point.available ? undefined : "4 4"}
              />
              <text
                x={label.x}
                y={label.y}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-foreground text-[10px]"
              >
                {t(`pillars.${point.id as PillarId}`)}
              </text>
              {!point.available && (
                <text
                  x={end.x}
                  y={end.y + 12}
                  textAnchor="middle"
                  className="fill-muted-foreground text-[9px]"
                >
                  {t("unavailable")}
                </text>
              )}
            </g>
          );
        })}
        {polygon ? (
          <polygon
            points={polygon}
            className="fill-primary/20 stroke-primary"
            strokeWidth="2"
          />
        ) : null}
        {points.map((point, index) => {
          if (!point.available || point.score === null) return null;
          const pos = radarAxisPoint(index, points.length, (point.score / 100) * RADIUS, CX, CY);
          return <circle key={`${point.id}-dot`} cx={pos.x} cy={pos.y} r="3.5" className="fill-primary" />;
        })}
      </svg>
      <table className="w-full text-sm">
        <caption className="sr-only">{t("radarTable")}</caption>
        <thead>
          <tr className="border-b text-left">
            <th className="py-2 font-medium">{t("radarTitle")}</th>
            <th className="py-2 font-medium">{t("score")}</th>
            <th className="py-2 font-medium">{t("confidence")}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.id} className="border-b last:border-0">
              <td className="py-2">{t(`pillars.${point.id as PillarId}`)}</td>
              <td className="py-2">
                {point.available && point.score !== null ? point.score : t("unavailable")}
              </td>
              <td className="py-2">
                {point.confidence === null
                  ? t("unavailable")
                  : `${Math.round(point.confidence * 100)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
