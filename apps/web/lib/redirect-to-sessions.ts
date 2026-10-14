import { getLocale } from "next-intl/server";
import { redirect } from "next/navigation";

export async function redirectToSessions(): Promise<never> {
  const locale = await getLocale();
  redirect(locale === "en" ? "/sessions" : `/${locale}/sessions`);
}
