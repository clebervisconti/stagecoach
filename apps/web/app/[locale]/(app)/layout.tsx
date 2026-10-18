import { auth } from "@/auth";
import { AppShell } from "@/components/shell/app-shell";
import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const privateBeta = process.env.PRIVATE_BETA_MODE === "true";
  const session = privateBeta ? null : await auth();
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;

  if (!session && !privateBeta) {
    redirect(`${prefix}/sign-in`);
  }

  return (
    <AppShell locale={locale} email={session?.user?.email || process.env.PRIVATE_BETA_EMAIL}>
      {children}
    </AppShell>
  );
}
