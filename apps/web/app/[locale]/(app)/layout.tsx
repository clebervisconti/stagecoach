import { auth } from "@/auth";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import Link from "next/link";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const privateBeta = process.env.PRIVATE_BETA_MODE === "true";
  const session = privateBeta ? null : await auth();
  const locale = await getLocale();
  const t = await getTranslations("nav");
  const prefix = locale === "en" ? "" : `/${locale}`;

  if (!session && !privateBeta) {
    redirect(`${prefix}/sign-in`);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-8">
            <Link href={`${prefix}/sessions`} className="text-xl font-bold">
              Stage Coach
            </Link>
            <nav className="flex gap-6">
              <Link
                href={`${prefix}/sessions`}
                className="text-sm font-medium hover:text-primary"
              >
                {t("sessions")}
              </Link>
              <Link
                href={`${prefix}/settings`}
                className="text-sm font-medium hover:text-primary"
              >
                {t("settings")}
              </Link>
              <Link
                href={`${prefix}/research`}
                className="text-sm font-medium hover:text-primary"
              >
                {t("research")}
              </Link>
              <Link
                href={`${prefix}/prep`}
                className="text-sm font-medium hover:text-primary"
                data-testid="nav-prep"
              >
                {t("prep")}
              </Link>
            </nav>
          </div>
          
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              {session?.user?.email || process.env.PRIVATE_BETA_EMAIL}
            </span>
            <Link
              href={locale === "en" ? "/pt-BR/sessions" : "/sessions"}
              className="text-sm font-medium hover:text-primary"
            >
              {locale === "en" ? "PT-BR" : "EN"}
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>
    </div>
  );
}
