import { AuthFrame } from "@/components/auth/auth-frame";
import { PrivacyDocument, loadPrivacyMarkdown } from "@/lib/privacy-doc";
import { titled } from "@/lib/titles";
import { getLocale } from "next-intl/server";

export function generateMetadata() {
  return titled("Privacy", "Privacidade");
}

export default async function PrivacyPage() {
  const locale = await getLocale();
  const note =
    locale === "pt-BR"
      ? "Este aviso está publicado em inglês."
      : "This notice is the current engineering draft. Counsel still reviews it before launch.";
  return (
    <AuthFrame width="prose">
      <PrivacyDocument markdown={loadPrivacyMarkdown()} />
      <p className="mt-10 text-sm text-[color:var(--text-tertiary)]">{note}</p>
    </AuthFrame>
  );
}
