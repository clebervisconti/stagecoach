import { auth, signOut } from "@/auth";
import { getTranslations } from "next-intl/server";
import { ConsentPanel } from "@/components/consents/consent-panel";
import { AccessibilityPanel } from "@/components/settings/accessibility-panel";
import { RetentionPanel } from "@/components/settings/retention-panel";

export default async function SettingsPage() {
  const session = await auth();
  const t = await getTranslations("settings");
  const email = session?.user?.email || process.env.PRIVATE_BETA_EMAIL;

  return (
    <div className="container mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-8 text-3xl font-bold">{t("heading")}</h1>

      <div className="space-y-6">
        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">{t("account")}</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("email")}</span>
              <span>{email}</span>
            </div>
          </div>
        </div>

        <ConsentPanel />

        <RetentionPanel />

        <AccessibilityPanel />

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
