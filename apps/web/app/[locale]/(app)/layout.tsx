import { auth } from "@/auth";
import { AppShell } from "@/components/shell/app-shell";
import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;

  if (!session?.user?.email) {
    redirect(`${prefix}/sign-in`);
  }
  if (session.user.mustChangePassword) {
    redirect(`${prefix}/account/password`);
  }

  return (
    <AppShell locale={locale} email={session.user.email} role={session.user.role}>
      {children}
    </AppShell>
  );
}
