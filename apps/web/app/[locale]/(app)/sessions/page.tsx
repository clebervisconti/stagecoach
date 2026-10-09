import { useTranslations } from "next-intl";

export default function SessionsPage() {
  const t = useTranslations("dashboard");

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("recentSessions")}</h1>
        <button className="rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90">
          {t("newSession")}
        </button>
      </div>

      <div className="rounded-lg border bg-card p-8 text-center text-card-foreground">
        <p className="text-muted-foreground">{t("noSessions")}</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Phase 0 - Sessions API not yet implemented
        </p>
      </div>
    </div>
  );
}
