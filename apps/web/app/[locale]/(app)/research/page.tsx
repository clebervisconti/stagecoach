import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { loadSourcesFromRepo } from "@/lib/load-sources";

export default async function ReferencesPage() {
  const t = await getTranslations("research");
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const sources = loadSourcesFromRepo();

  return (
    <div className="container mx-auto max-w-3xl px-4 py-10" data-testid="references-page">
      <h1 className="text-3xl font-semibold">{t("heading")}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t("intro")}</p>
      <p className="mt-3 flex flex-wrap gap-4 text-sm">
        <Link className="text-primary underline-offset-2 hover:underline" href={`${prefix}/research/myths`}>
          {t("mythsHeading")}
        </Link>
        <Link className="text-primary underline-offset-2 hover:underline" href={`${prefix}/config/scoring`}>
          {t("scoringHeading", { version: "1.0.0" })}
        </Link>
      </p>
      <ol className="mt-8 space-y-6">
        {sources.map((source, index) => (
          <li key={source.key} id={source.anchor} className="scroll-mt-24">
            {index === 0 || sources[index - 1]?.section !== source.section ? (
              <h2 className="mb-3 text-lg font-medium text-foreground">{source.section}</h2>
            ) : null}
            <p>
              <span className="font-mono text-sm font-semibold">[{source.key}]</span> {source.text}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}
