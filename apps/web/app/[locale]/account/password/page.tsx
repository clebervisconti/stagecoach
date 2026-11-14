import { auth } from "@/auth";
import { PasswordForm } from "@/components/auth/password-form";
import { titled } from "@/lib/titles";
import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

export function generateMetadata() {
  return titled("Change password", "Alterar senha");
}

export const dynamic = "force-dynamic";

export default async function PasswordPage() {
  const session = await auth();
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;
  if (!session?.user?.email) redirect(`${prefix}/sign-in`);

  return <PasswordForm forced={Boolean(session.user.mustChangePassword)} />;
}
