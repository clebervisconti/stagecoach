import type { Metadata } from "next";
import { getLocale } from "next-intl/server";

export async function titled(en: string, pt: string): Promise<Metadata> {
  const locale = await getLocale();
  return { title: locale === "pt-BR" ? pt : en, robots: { index: false, follow: false } };
}
