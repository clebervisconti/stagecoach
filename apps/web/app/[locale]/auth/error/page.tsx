import Link from "next/link";
import { AuthFrame } from "@/components/auth/auth-frame";
import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Authentication error", "Erro de autenticação");
}

const COPY = {
  en: {
    heading: "Sign-in could not be completed",
    body: "Start again from the sign-in page.",
    action: "Back to sign in",
  },
  "pt-BR": {
    heading: "Não foi possível concluir a entrada",
    body: "Comece de novo na página de acesso.",
    action: "Voltar para entrar",
  },
} as const;

export default async function AuthErrorPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const prefix = locale === "pt-BR" ? "/pt-BR" : "";
  return (
    <AuthFrame>
      <h1 className="text-3xl">{t.heading}</h1>
      <p className="mt-3 text-base leading-[26px] text-[color:var(--text-secondary)]">{t.body}</p>
      <Link href={`${prefix}/sign-in`} className="cs-button cs-button-primary mt-8">
        {t.action}
      </Link>
    </AuthFrame>
  );
}
