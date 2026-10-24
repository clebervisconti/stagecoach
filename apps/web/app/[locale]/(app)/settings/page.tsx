import { auth, signOut } from "@/auth";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { ConsentPanel } from "@/components/consents/consent-panel";
import { AccessibilityPanel } from "@/components/settings/accessibility-panel";
import { RetentionPanel } from "@/components/settings/retention-panel";
import { AiProvidersPanel } from "@/components/settings/ai-providers-panel";
import { AccountRightsPanel } from "@/components/settings/account-rights-panel";

export default async function SettingsPage() {
  const session = await auth();
  const t = await getTranslations("settings");
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const email = session?.user?.email;

  return (
    <div className="container mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-8 text-3xl font-bold">{t("heading")}</h1>

      <div className="space-y-6">
        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">{t("account")}</h2>
          <div className="space-y-2">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">{t("email")}</span>
              <span className="break-all">{email}</span>
            </div>
            <Link href={`${prefix}/account/password`} className="inline-block text-sm underline">
              {t("changePassword")}
            </Link>
          </div>
        </div>

        <ConsentPanel />

        <AiProvidersPanel />

        <RetentionPanel />

        <AccessibilityPanel />

        <AccountRightsPanel />

        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">Session</h2>
          <form
            action={async () => {
              "use server";
              await signOut();
            }}
          >
            <button
              type="submit"
              className="rounded-md border border-input bg-background px-4 py-2 font-medium hover:bg-accent hover:text-accent-foreground"
            >
              {t("signOut")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
