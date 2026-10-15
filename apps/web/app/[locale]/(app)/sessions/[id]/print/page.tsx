"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { CategoryCards } from "@/components/report/category-cards";
import { InsightsPanel } from "@/components/report/insights-panel";
import { KeyMetrics } from "@/components/report/key-metrics";
import { RadarChart } from "@/components/report/radar-chart";
import { SummaryCard } from "@/components/report/summary-card";
import { TranscriptTab } from "@/components/report/transcript-tab";
import type { AnalysisReport } from "@/lib/report-types";
import { radarPoints } from "@/lib/report-view";
import { formatTimestamp } from "@/lib/player";
import type { TranscriptPayload } from "@/lib/transcript";

function isReport(value: unknown): value is AnalysisReport {
  if (!value || typeof value !== "object") return false;
  const candidate = value as AnalysisReport;
  return Boolean(candidate.overall && candidate.pillars && candidate.categories && candidate.insights);
}

export default function PrintReportPage() {
  const t = useTranslations("report");
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const includeTranscript = search.get("includeTranscript") === "1";
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [transcript, setTranscript] = useState<TranscriptPayload | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      const reportResponse = await fetch(`/api/stagecoach/sessions/${params.id}/report`, {
        cache: "no-store",
      });
      if (reportResponse.ok) {
        const payload: unknown = await reportResponse.json();
        if (isReport(payload) && active) setReport(payload);
      }
      if (includeTranscript) {
        const transcriptResponse = await fetch(`/api/stagecoach/sessions/${params.id}/transcript`, {
          cache: "no-store",
        });
        if (transcriptResponse.ok && active) setTranscript(await transcriptResponse.json());
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [params.id, includeTranscript]);

  if (!report) {
    return <p className="p-8 text-sm text-muted-foreground">{t("loadError")}</p>;
  }

  const version = report.provenance?.scoring_config_version ?? "1.0.0";
  const generated = report.provenance?.generated_at ?? "";
  const durationMin = report.media?.duration_s ? report.media.duration_s / 60 : null;

  return (
    <div data-testid="pdf-print" className="mx-auto max-w-3xl space-y-8 bg-white p-8 text-zinc-900">
      <section data-section="cover">
        <p className="text-sm text-muted-foreground">Stage Coach</p>
        <SummaryCard report={report} />
        <RadarChart points={radarPoints(report)} />
        <KeyMetrics report={report} />
      </section>
      <section data-section="opportunities">
        <h2 className="mb-3 text-xl font-semibold">{t("opportunities")}</h2>
        <InsightsPanel report={report} />
        <ul className="mt-3 space-y-2 text-sm">
          {(report.insights.opportunities ?? []).slice(0, 3).map((item) => {
            const ev = (report.evidence ?? []).find((row) => item.evidence_ids?.includes(row.id));
            return (
              <li key={item.title}>
                {ev ? (
                  <span>
                    {t("keyframe")} {formatTimestamp(ev.t_start)}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>
      <section data-section="strengths">
        <h2 className="mb-3 text-xl font-semibold">{t("strengths")}</h2>
      </section>
      <section data-section="categories">
        <h2 className="mb-3 text-xl font-semibold">{t("categories")}</h2>
        <CategoryCards report={report} />
      </section>
      <section data-section="time">
        <h2 className="mb-3 text-xl font-semibold">{t("timeBreakdown")}</h2>
        <p className="text-sm">
          {durationMin != null ? `${durationMin.toFixed(1)} ${t("minutes")}` : t("metricNA")}
        </p>
      </section>
      <section data-section="metrics">
        <h2 className="mb-3 text-xl font-semibold">{t("metricsTrend")}</h2>
        <KeyMetrics report={report} />
      </section>
      <section data-section="drills">
        <h2 className="mb-3 text-xl font-semibold">{t("drills")}</h2>
        <ul className="list-disc pl-5 text-sm">
          {(report.insights.opportunities ?? [])
            .flatMap((item) => item.drill_ids ?? [])
            .map((drill) => (
              <li key={drill}>{drill}</li>
            ))}
        </ul>
      </section>
      <section data-section="methodology">
        <h2 className="mb-3 text-xl font-semibold">{t("methodology")}</h2>
        <p className="text-sm">
          {t("scoringVersion")}: {version}
        </p>
        <p className="text-sm text-muted-foreground">{t("pdfLimitations")}</p>
      </section>
      {includeTranscript && (
        <section data-section="transcript" data-testid="pdf-transcript">
          <h2 className="mb-3 text-xl font-semibold">{t("transcript")}</h2>
          <TranscriptTab payload={transcript} onSeek={() => undefined} />
        </section>
      )}
      <footer className="text-xs text-muted-foreground">
        {generated} · {version}
      </footer>
    </div>
  );
}
