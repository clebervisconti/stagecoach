import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Info } from "lucide-react";
import { CATEGORY_IDS, type AnalysisReport } from "@/lib/report-types";
import { isNaCode } from "@/lib/online";

export function NotMeasured({ report }: { report: AnalysisReport }) {
  const t = useTranslations("online");
  const reportT = useTranslations("report");
  const locale = useLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const rows = report.categories.filter((category) => !category.applicable || category.score == null);
  if (!rows.length) return null;
  return (
    <section data-testid="not-measured" className="rounded-[var(--radius-sm)] border border-[color:var(--line)] p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="cs-eyebrow">{t("notMeasured")}</h2>
        <p className="font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
          {t("notMeasuredCount", { n: String(rows.length), of: String(report.categories.length) })}
        </p>
      </div>
      <p className="mt-2 text-sm text-[color:var(--text-secondary)]">{t("notMeasuredLead")}</p>
      <ul className="mt-6 grid gap-4 md:grid-cols-2">
        {rows.map((category) => {
          const code = isNaCode(category.na_code) ? category.na_code : null;
          const reason = code
            ? t(`na.${code}`)
            : category.id === "screen_flow"
              ? t("na.screenFlowSoon")
              : category.na_reason || t("na.not_applicable");
          return (
            <li key={category.id} className="flex items-start gap-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--text-tertiary)]" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium">
                  {(CATEGORY_IDS as readonly string[]).includes(category.id)
                    ? reportT(`categoriesNamed.${category.id}`)
                    : category.id.replaceAll("_", " ")}
                </p>
                <p className="mt-1 text-sm text-[color:var(--text-secondary)]">{reason}</p>
                {code === "consent_video_off" && (
                  <Link href={`${prefix}/settings`} className="mt-2 inline-block text-xs uppercase tracking-[0.08em]">
                    {t("openSettings")}
                  </Link>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
