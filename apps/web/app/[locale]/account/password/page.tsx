import { auth } from "@/auth";
import { PasswordForm } from "@/components/auth/password-form";
import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function PasswordPage() {
  const session = await auth();
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;
  if (!session?.user?.email) redirect(`${prefix}/sign-in`);

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full min-w-0 max-w-md">
        <PasswordForm forced={Boolean(session.user.mustChangePassword)} />
      </div>
    </div>
  );
}
