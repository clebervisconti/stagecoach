import { getTranslations } from "next-intl/server";
import { PlanForm } from "@/components/prep/plan-form";

export default async function PrepPage() {
  const t = await getTranslations("planForm");
  return (
    <div className="container mx-auto max-w-3xl px-4 py-8" data-testid="prep-page">
      <h1 className="mb-2 text-3xl font-bold">{t("heading")}</h1>
      <p className="mb-8 text-sm text-muted-foreground">{t("intro")}</p>
      <PlanForm />
    </div>
  );
}
