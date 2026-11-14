import Link from "next/link";
import { AuthFrame } from "@/components/auth/auth-frame";
import { getLocale } from "next-intl/server";

const COPY = {
  en: {
    heading: "Page not found",
    body: "That address is not in Stage Coach.",
    action: "Go to sessions",
  },
  "pt-BR": {
    heading: "Página não encontrada",
    body: "Esse endereço não existe no Stage Coach.",
    action: "Ir para as sessões",
  },
} as const;

export default async function NotFound() {
  const locale = await getLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const prefix = locale === "pt-BR" ? "/pt-BR" : "";
  return (
    <AuthFrame>
      <h1 className="text-3xl">{t.heading}</h1>
      <p className="mt-3 text-base leading-[26px] text-[color:var(--text-secondary)]">{t.body}</p>
      <Link href={`${prefix}/sessions`} className="cs-button cs-button-primary mt-8">
        {t.action}
      </Link>
    </AuthFrame>
  );
}
