import { useTranslations } from "next-intl";
import Link from "next/link";

export default function AuthErrorPage({
  searchParams,
}: {
  searchParams: { error?: string };
}) {
  const t = useTranslations("common");
  const error = searchParams.error;

  const errorMessages: Record<string, string> = {
    Configuration: "There is a problem with the server configuration.",
    AccessDenied: "You do not have permission to sign in.",
    Verification: "The verification link is invalid or has expired.",
    Default: "An error occurred during authentication.",
  };

  const message = error && errorMessages[error] ? errorMessages[error] : errorMessages.Default;

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50 px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <svg
              className="h-8 w-8 text-destructive"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          
          <h1 className="text-2xl font-bold">{t("error")}</h1>
          <p className="mt-2 text-muted-foreground">{message}</p>
        </div>

        <div className="text-center">
          <Link
            href="/sign-in"
            className="inline-block rounded-md bg-primary px-6 py-2 font-medium text-primary-foreground hover:bg-primary/90"
          >
            Try again
          </Link>
        </div>
      </div>
    </div>
  );
}
