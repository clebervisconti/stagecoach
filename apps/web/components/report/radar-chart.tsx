"use client";

import { useTranslations } from "next-intl";
import type { PillarId } from "@/lib/report-types";
import { radarAxisPoint, radarPolygon, type RadarPoint } from "@/lib/report-view";

const PAD = 48;
const SIZE = 280 + PAD * 2;
const CX = 140 + PAD;
const CY = 140 + PAD;
const RADIUS = 96;

function wrapLabel(text: string): string[] {
  if (text.length <= 14) return [text];
  const split = text.lastIndexOf(" ", 14);
  const at = split > 4 ? split : 14;
  const second = text.slice(at).trim();
  return second ? [text.slice(0, at).trim(), second] : [text];
}

type RadarChartProps = {
  points: RadarPoint[];
  goalPoints?: RadarPoint[];
};

export function RadarChart({ points, goalPoints }: RadarChartProps) {
  const t = useTranslations("report");
  const available = points.filter((point) => point.available);
  const availableGoals = goalPoints?.filter((point) => point.available);
  const polygon = radarPolygon(available, RADIUS, CX, CY);
  const goalPolygon = availableGoals ? radarPolygon(availableGoals, RADIUS, CX, CY) : "";
  const rings = [0.25, 0.5, 0.75, 1];
  const axes = available.length ? available : points;

  return (
    <figure className="space-y-4">
      <figcaption className="text-sm font-medium">{t("radarCaption")}</figcaption>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        overflow="visible"
        role="img"
        aria-hidden="true"
        className="mx-auto h-80 w-80"
      >
        <defs>
          <pattern id="radar-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" className="fill-primary/15" />
            <line x1="0" y1="0" x2="0" y2="6" className="stroke-primary" strokeWidth="2" />
          </pattern>
        </defs>
        {rings.map((ring) => {
          const ringPoints = axes
            .map((_, index) => radarAxisPoint(index, axes.length, RADIUS * ring, CX, CY))
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
        {axes.map((point, index) => {
          const end = radarAxisPoint(index, axes.length, RADIUS, CX, CY);
          const label = radarAxisPoint(index, axes.length, RADIUS + 22, CX, CY);
          return (
            <g key={point.id}>
              <line x1={CX} y1={CY} x2={end.x} y2={end.y} className="stroke-border" />
              <text
                x={label.x}
                y={label.y}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-foreground text-[10px]"
              >
                {wrapLabel(t(`pillars.${point.id as PillarId}`)).map((line, lineIndex, lines) => (
                  <tspan key={line} x={label.x} dy={lineIndex === 0 ? (lines.length > 1 ? "-0.5em" : "0") : "1.1em"}>
                    {line}
                  </tspan>
                ))}
              </text>
            </g>
          );
        })}
        {goalPolygon ? (
          <polygon
            points={goalPolygon}
            fill="none"
            className="stroke-primary"
            strokeWidth="2"
            strokeDasharray="6 4"
            data-testid="goal-polygon"
          />
        ) : null}
        {(availableGoals ?? []).map((point, index) => {
          if (point.score === null) return null;
          const pos = radarAxisPoint(index, axes.length, (point.score / 100) * RADIUS, CX, CY);
          return (
            <circle
              key={`${point.id}-goal`}
              cx={pos.x}
              cy={pos.y}
              r="4"
              className="fill-background stroke-primary"
              strokeWidth="2"
              strokeDasharray="3 2"
              data-testid="goal-vertex"
            />
          );
        })}
        {polygon ? (
          <polygon
            points={polygon}
            fill="color-mix(in srgb, var(--data-1) 8%, transparent)"
            stroke="var(--data-1)"
            strokeWidth="1.5"
          />
        ) : null}
        {axes.map((point, index) => {
          if (point.score === null) return null;
          const pos = radarAxisPoint(index, axes.length, (point.score / 100) * RADIUS, CX, CY);
          return <circle key={`${point.id}-dot`} cx={pos.x} cy={pos.y} r="3.5" fill="var(--data-1)" />;
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
