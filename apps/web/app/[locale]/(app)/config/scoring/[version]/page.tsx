import { getTranslations } from "next-intl/server";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { notFound } from "next/navigation";
import { CATEGORY_IDS } from "@/lib/report-types";

type PageProps = {
  params: Promise<{ version: string }>;
};

function scoringPath(version: string): string | null {
  if (!version || version.includes("/") || version.includes("..")) return null;
  const path = join(process.cwd(), `../../packages/scoring-config/v${version}/scoring.yaml`);
  return existsSync(path) ? path : null;
}

export default async function ScoringConfigPage({ params }: PageProps) {
  const { version } = await params;
  const t = await getTranslations("research");
  const path = scoringPath(version);
  if (!path) notFound();
  const yaml = readFileSync(path, "utf8");

  return (
    <div className="container mx-auto max-w-4xl px-4 py-10" data-testid="scoring-config-page">
      <h1 className="text-3xl font-semibold">{t("scoringHeading", { version })}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t("scoringIntro")}</p>
      <p className="mt-2 text-xs text-muted-foreground">{t("scoringReadonly")}</p>
      <section className="mt-8">
        <h2 className="text-lg font-medium">{t("scoringCategories")}</h2>
        <ul className="mt-3 grid gap-2 text-sm md:grid-cols-2">
          {CATEGORY_IDS.map((id) => (
            <li key={id} className="rounded-md border bg-card px-3 py-2 font-mono">
              {id}
            </li>
          ))}
        </ul>
      </section>
      <details className="mt-8 rounded-lg border bg-muted/40 p-4">
        <summary className="cursor-pointer font-medium">{t("scoringRaw")}</summary>
        <pre className="mt-3 overflow-x-auto text-xs" data-testid="scoring-config-yaml">
          {yaml}
        </pre>
      </details>
    </div>
  );
}
