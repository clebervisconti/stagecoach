"use client";

import Link from "next/link";
import { useLocale } from "next-intl";
import type { ReactNode } from "react";
import { BrandLockup } from "@/components/brand/brand-lockup";

const COPY = {
  en: {
    promise: "Upload or record a talk. Get research-backed feedback.",
    skip: "Skip to content",
    privacy: "Privacy",
  },
  "pt-BR": {
    promise: "Envie ou grave uma palestra. Receba um retorno baseado em pesquisa.",
    skip: "Pular para o conteúdo",
    privacy: "Privacidade",
  },
} as const;

export function AuthFrame({
  children,
  width = "form",
}: {
  children: ReactNode;
  width?: "form" | "prose";
}) {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const prefix = locale === "pt-BR" ? "/pt-BR" : "";
  return (
    <>
      <a href="#main" className="cs-skip">
        {t.skip}
      </a>
      <main id="main" className="min-h-screen px-6 py-8 md:px-16 md:py-12">
        <div className={width === "form" ? "max-w-md" : "max-w-3xl"}>
          <BrandLockup />
          <p className="mt-4 max-w-prose text-base leading-[26px] text-[color:var(--text-secondary)]">{t.promise}</p>
          <div className="mt-10">{children}</div>
          <footer className="mt-16 border-t border-[color:var(--line)] pt-6">
            <Link href={`${prefix}/privacy`} className="cs-text-link">
              {t.privacy}
            </Link>
          </footer>
        </div>
      </main>
    </>
  );
}
