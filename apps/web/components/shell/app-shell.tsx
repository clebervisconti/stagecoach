"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

type AppShellProps = {
  locale: string;
  email?: string | null;
  children: React.ReactNode;
};

const LINKS = [
  { key: "sessions", href: "/sessions", testId: undefined },
  { key: "prep", href: "/prep", testId: "nav-prep" },
  { key: "trends", href: "/trends", testId: "nav-trends" },
  { key: "research", href: "/research", testId: undefined },
  { key: "settings", href: "/settings", testId: undefined },
] as const;

export function AppShell({ locale, email, children }: AppShellProps) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("cs-theme", next);
    setTheme(next);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center justify-between gap-4 border-b px-4 md:px-6">
        <Link href={`${prefix}/sessions`} className="flex flex-col leading-none">
          <span className="cs-eyebrow">Cybersphere</span>
          <span className="cs-product">Stage Coach</span>
        </Link>
        <div className="flex items-center gap-3">
          {email ? (
            <span className="hidden max-w-[220px] truncate text-sm text-muted-foreground sm:inline">
              {email}
            </span>
          ) : null}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? t("themeToLightAria") : t("themeToDarkAria")}
            className="px-3 py-2 text-xs"
          >
            {theme === "dark" ? t("themeToLight") : t("themeToDark")}
          </button>
          <Link href={locale === "en" ? "/pt-BR/sessions" : "/sessions"} className="cs-nav-link border-0 px-2">
            {locale === "en" ? "PT-BR" : "EN"}
          </Link>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <nav className="hidden w-60 shrink-0 flex-col border-r py-4 md:flex" aria-label={t("home")}>
          {LINKS.map((link) => {
            const href = `${prefix}${link.href}`;
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={link.key}
                href={href}
                data-testid={link.testId}
                data-active={active ? "true" : "false"}
                className="cs-nav-link"
              >
                {t(link.key)}
              </Link>
            );
          })}
        </nav>
        <div className="flex min-w-0 flex-1 flex-col">
          <nav className="flex flex-wrap border-b md:hidden" aria-label={t("home")}>
            {LINKS.map((link) => {
              const href = `${prefix}${link.href}`;
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={link.key}
                  href={href}
                  data-testid={link.testId}
                  data-active={active ? "true" : "false"}
                  className="cs-nav-link border-b-2 border-l-0 px-3"
                >
                  {t(link.key)}
                </Link>
              );
            })}
          </nav>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </div>
  );
}
