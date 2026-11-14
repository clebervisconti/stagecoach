"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Check, ChevronRight, CircleAlert, CircleX, Loader2, Minus } from "lucide-react";
import type { AnalysisReport } from "@/lib/report-types";
import { CATEGORY_IDS } from "@/lib/report-types";
import { averageLast, metricNumber, overallFinding, type ScorePoint } from "@/lib/overview";

type SessionRow = {
  id: string;
  title: string;
  status: string;
  context_type: string;
  created_at: string;
  overall: number | null;
  href: string;
};

export function SessionsHome({
  greeting,
  sessions,
  loading,
  error,
  briefing,
  points,
  locale,
  prefix,
  onNew,
  onAdded,
  toast,
  onUndo,
  children,
}: {
  greeting: string;
  sessions: SessionRow[];
  loading: boolean;
  error: string;
  briefing: AnalysisReport | null;
  points: ScorePoint[];
  locale: string;
  prefix: string;
  onNew: () => void;
  onAdded: () => void;
  toast: string;
  onUndo: () => void;
  children?: ReactNode;
}) {
  const t = useTranslations("dashboard");
  const signal = useTranslations("signal");
  const report = useTranslations("report");
  const scored = points;
  const windowCount = Math.min(3, scored.length);
  const average = averageLast(scored, windowCount);
  const finding = overallFinding(scored);
  const pace = metricNumber(briefing?.metrics, "pp_wpm");
  const fillers = metricNumber(briefing?.metrics, "fl_filler_sounds_per_min");
  const latest = [...sessions].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];
  const opportunities = briefing?.insights.opportunities.slice(0, 2) ?? [];
  const summary = briefing?.insights.summary?.trim() ?? "";

  return (
    <div className="grid gap-4" data-testid="sessions-overview">
      <div className="k-col" style={{ gap: 6 }}>
        <h1 suppressHydrationWarning>{greeting}</h1>
        <p className="k-sec" style={{ fontSize: 14 }}>
          {scored.length
            ? signal("sessionsMeta", {
                count: String(scored.length),
                when: latest ? relativeWhen(latest.created_at, locale) : signal("noReportsYet"),
              })
            : signal("noReportsYet")}
        </p>
        {sessions.length > 0 ? (
          <button type="button" className="cs-button cs-button-ghost" data-testid="new-session" onClick={onNew} style={{ width: "fit-content" }}>
            {signal("actionNew")}
          </button>
        ) : null}
      </div>

      {error ? (
        <div role="alert" className="cs-alert cs-alert-critical">
          <div className="cs-alert-body">{error}</div>
        </div>
      ) : null}

      {children}

      {loading && sessions.length === 0 && !children ? (
        <div className="grid gap-3" data-testid="sessions-loading" aria-busy="true">
          <div className="k-skel" style={{ height: 96 }} />
          <div className="k-skel" style={{ height: 56 }} />
          <div className="k-skel" style={{ height: 56 }} />
        </div>
      ) : null}

      {!loading && sessions.length === 0 && !children ? (
        <section className="cs-panel cs-empty" data-testid="empty-sessions">
          <h2 className="cs-panel-title">{signal("emptyTitle")}</h2>
          <p className="k-sec" style={{ maxWidth: 560 }}>{signal("emptyBody")}</p>
          <div className="k-row">
            <button type="button" className="cs-button cs-button-primary" data-testid="new-session" onClick={onNew}>{signal("emptyPrimary")}</button>
            <Link href={`${prefix}/config/scoring`} className="cs-button cs-button-ghost">{signal("emptySecondary")}</Link>
          </div>
          <p className="k-note">{signal("emptyNote")}</p>
        </section>
      ) : null}

      {summary || opportunities.length ? (
        <section className="cs-panel" aria-labelledby="coach-brief" data-testid="coach-briefing">
          <div className="k-between">
            <span className="s-label">{signal("coachBriefing")}</span>
            <span className="k-mono k-ter" style={{ fontSize: 12 }}>{signal("reportsRead", { count: String(scored.length) })}</span>
          </div>
          {summary ? <h2 id="coach-brief" className="k-ai-sum">{summary}</h2> : <h2 id="coach-brief" className="cs-sr-only">{signal("coachBriefing")}</h2>}
          {opportunities.length ? (
            <div className="k-g3">
              {opportunities.map((item) => (
                <div key={`${item.category_id}-${item.title}`} className="k-card">
                  <p style={{ fontSize: 15 }}>{item.fix || item.body}</p>
                  <div className="k-row" style={{ marginTop: "auto" }}>
                    <button type="button" className="cs-button cs-button-primary" onClick={() => { if (item.drill_ids[0]) window.sessionStorage.setItem("sc-practice-drill", item.drill_ids[0]); onAdded(); }}>
                      {signal("addToPractice")}
                    </button>
                    <Link className="cs-button cs-button-ghost" href={item.drill_ids[0] ? `${prefix}/practice?drill=${encodeURIComponent(item.drill_ids[0])}` : `${prefix}/sessions`}>
                      {signal("details")}
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          <p className="k-src">
            <span>{signal("sources")}: </span>
            {opportunities.map((item) => (
              <span key={item.category_id} className="cs-kbd" style={{ marginRight: 6 }}>
                {categoryName(item.category_id, report)}
              </span>
            ))}
          </p>
        </section>
      ) : null}

      {sessions.length > 0 ? (
        <>
          <div className="k-g4">
            <Kpi
              label={signal(windowCount === 1 ? "overallLastOne" : "overallLast", { count: String(windowCount) })}
              value={average === null ? "—" : String(average)}
            />
            <Kpi label={signal("pace")} value={pace === null ? "—" : String(Math.round(pace))} note={pace === null ? signal("notMeasured") : undefined} />
            <Kpi label={signal("fillers")} value={fillers === null ? "—" : fillers.toFixed(1)} note={fillers === null ? signal("notMeasured") : undefined} />
          </div>
          <div className="k-g2">
            {scored.length > 0 ? (
              <ScoreChart
                title={finding ?? signal("trendsAfter")}
                caption={signal("chartMeta")}
                source={signal("chartSource")}
                note={scored.length < 3 && finding ? signal("trendsAfter") : undefined}
                lined={scored.length >= 3}
                points={scored}
                locale={locale}
              />
            ) : null}
            <section className="cs-panel">
              <div className="k-between">
                <h2 className="cs-panel-title">{signal("recent")}</h2>
                <button type="button" className="cs-button cs-button-ghost" onClick={onNew}>
                  {signal("actionNew")}
                </button>
              </div>
              <div className="cs-session-head" aria-hidden="true">
                <span>{t("title")}</span>
                <span>{locale.startsWith("pt") ? "Estado" : "Status"}</span>
                <span>{report("score")}</span>
                <span className="cs-session-date">{locale.startsWith("pt") ? "Data" : "Date"}</span>
                <span />
              </div>
              <ul className="cs-session-list">
                {sessions.map((session) => (
                  <li key={session.id}>
                    <Link className="cs-session-row" href={session.href}>
                      <span>
                        <span className="k-strong">{session.title}</span>
                        <br />
                        <span className="k-ter" style={{ fontSize: 14 }}>{session.context_type.replaceAll("_", " ")}</span>
                      </span>
                      <span className="cs-session-status"><Status status={session.status} label={statusLabel(session.status, t)} /></span>
                      <span className="cs-num">{typeof session.overall === "number" ? Math.round(session.overall) : "—"}</span>
                      <span className="cs-session-date cs-num k-ter">{new Date(session.created_at).toLocaleDateString(locale, { month: "short", day: "numeric" })}</span>
                      <ChevronRight className="h-4 w-4" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      ) : null}

      {toast ? (
        <div className="k-toast" role="status">
          <span>{toast}</span>
          <button type="button" className="cs-button cs-button-ghost" onClick={onUndo}>{signal("undo")}</button>
        </div>
      ) : null}
    </div>
  );

}

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="cs-kpi">
      <span className="k-sec" style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
      <p className="stat-m">{value}</p>
      {note ? <p className="k-note">{note}</p> : null}
    </div>
  );
}

function ScoreChart({ title, caption, source, note, lined, points, locale }: { title: string; caption: string; source: string; note?: string; lined: boolean; points: ScorePoint[]; locale: string }) {
  const width = 640;
  const height = 180;
  const pad = 16;
  const values = points.map((point) => point.overall);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const coords = points.map((point, index) => {
    const x = pad + (index * (width - pad * 2)) / Math.max(1, points.length - 1);
    const y = pad + (1 - (point.overall - min) / span) * (height - pad * 2);
    return `${x},${y}`;
  });
  const label = `${title}. ${points.map((point) => Math.round(point.overall)).join(", ")}`;
  return (
    <section className="cs-panel">
      <h2 className="cs-panel-title">{title}</h2>
      <p className="cs-panel-meta">{caption}</p>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        {lined ? <polyline fill="none" stroke="var(--data-1)" strokeWidth="2" points={coords.join(" ")} /> : null}
        {coords.map((coord, index) => {
          const [x, y] = coord.split(",");
          return <circle key={points[index]?.at ?? coord} cx={x} cy={y} r={lined ? 0 : 4} fill="var(--data-1)" />;
        })}
      </svg>
      {note ? <p className="cs-panel-meta">{note}</p> : null}
      <div className="k-between k-mono k-ter" style={{ fontSize: 11 }}>
        <span>{new Date(points[0].at).toLocaleDateString(locale, { month: "short", day: "numeric" })}</span>
        <span>{new Date(points[points.length - 1].at).toLocaleDateString(locale, { month: "short", day: "numeric" })}</span>
      </div>
      <p className="k-src">{source}</p>
    </section>
  );
}

function Status({ status, label }: { status: string; label: string }) {
  const Icon = status === "ready" ? Check : status === "failed" ? CircleX : status === "partial" || status === "layout_review" ? CircleAlert : status === "processing" || status === "uploaded" || status === "preparing" ? Loader2 : Minus;
  const tone = status === "ready" ? "cs-status-success" : status === "failed" ? "cs-status-critical" : status === "partial" || status === "layout_review" ? "cs-status-warning" : "cs-status-info";
  return (
    <span className={`${tone} px-3 py-1`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}

function categoryName(id: string, t: ReturnType<typeof useTranslations<"report">>) {
  if ((CATEGORY_IDS as readonly string[]).includes(id)) return t(`categoriesNamed.${id as (typeof CATEGORY_IDS)[number]}`);
  return id.replaceAll("_", " ");
}

function relativeWhen(iso: string, locale: string) {
  const date = new Date(iso);
  const days = Math.round((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(0, "day");
  if (days < 30) return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(-days, "day");
  return date.toLocaleDateString(locale, { month: "short", day: "numeric" });
}

function statusLabel(
  status: string,
  t: (
    key:
      | "statusReady"
      | "statusFailed"
      | "statusPartial"
      | "statusProcessing"
      | "statusCreated"
      | "statusPreparing"
      | "statusLayoutReview",
  ) => string,
): string {
  if (status === "ready") return t("statusReady");
  if (status === "failed") return t("statusFailed");
  if (status === "partial") return t("statusPartial");
  if (status === "preparing") return t("statusPreparing");
  if (status === "layout_review") return t("statusLayoutReview");
  if (status === "processing" || status === "uploaded") return t("statusProcessing");
  return t("statusCreated");
}
