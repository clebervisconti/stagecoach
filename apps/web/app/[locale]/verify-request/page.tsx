import { useTranslations } from "next-intl";

export default function VerifyRequestPage({
  searchParams,
}: {
  searchParams: { email?: string };
}) {
  const t = useTranslations("auth");
  const email = searchParams.email || "";

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50 px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <svg
              className="h-8 w-8 text-primary"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          </div>
          
          <h1 className="text-2xl font-bold">{t("checkEmail")}</h1>
          <p className="mt-2 text-muted-foreground">
            {t("magicLinkSent", { email })}
          </p>
        </div>

        <div className="rounded-lg bg-card p-6 shadow">
          <p className="text-sm text-muted-foreground">
            Click the link in the email to sign in. You can close this window.
          </p>
        </div>

        <div className="text-center">
          <a
            href="/sign-in"
            className="text-sm text-primary hover:underline"
          >
            Try a different email
          </a>
        </div>
      </div>
    </div>
  );
}
