import { auth } from "@/auth";
import { AdminUsersPanel } from "@/components/admin/users-panel";
import { titled } from "@/lib/titles";
import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

export function generateMetadata() {
  return titled("Users", "Usuários");
}

export const dynamic = "force-dynamic";

export default async function AdminUsersPage() {
  const session = await auth();
  const locale = await getLocale();
  const prefix = locale === "en" ? "" : `/${locale}`;
  if (!session?.user?.email) redirect(`${prefix}/sign-in`);
  if (session.user.mustChangePassword) redirect(`${prefix}/account/password`);
  if (session.user.role !== "admin") redirect(`${prefix}/sessions`);
  return <AdminUsersPanel />;
}
