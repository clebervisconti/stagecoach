import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { referencesHref } from "@/lib/research-sources";

const ITEMS = [
  { id: "no73855", source: "S20" },
  { id: "noEmotion", source: "S29" },
  { id: "noAccent", source: "S54" },
  { id: "moreNotBetter", source: "S27" },
  { id: "heuristics", source: null },
] as const;

export default async function MythsPage() {
  const t = await getTranslations("research");
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;

  return (
    <div className="container mx-auto max-w-3xl px-4 py-10" data-testid="myths-page">
      <h1 className="text-3xl font-semibold">{t("mythsHeading")}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t("mythsIntro")}</p>
      <ul className="mt-8 space-y-6">
        {ITEMS.map((item) => (
          <li key={item.id} className="rounded-lg border bg-card p-5">
            <h2 className="font-semibold">{t(`myths.${item.id}Title`)}</h2>
            <p className="mt-2 text-sm">{t(`myths.${item.id}Body`)}</p>
            {item.source ? (
              <p className="mt-3 text-sm">
                <Link
                  className="font-mono text-primary underline-offset-2 hover:underline"
                  href={referencesHref(item.source, prefix)}
                >
                  [{item.source}]
                </Link>
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
