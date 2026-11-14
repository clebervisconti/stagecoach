"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ChartLine, Dumbbell, FileText, LayoutList, Settings, Sparkles, Users } from "lucide-react";
import { CompactMark } from "@/components/brand/brand-lockup";
import { SessionWatch } from "@/components/shell/session-watch";
import { CommandPalette, useCommandShortcut, type PaletteAction } from "@/components/shell/command-palette";
import { useTheme } from "@/components/shell/use-theme";

type AppShellProps = {
  locale: string;
  email?: string | null;
  role?: string | null;
  children: React.ReactNode;
};

const RAIL = [
  { key: "sessions", href: "/sessions", testId: "nav-sessions", icon: LayoutList },
  { key: "practice", href: "/practice", testId: "nav-practice", icon: Dumbbell },
  { key: "prep", href: "/prep", testId: "nav-prep", icon: FileText },
  { key: "trends", href: "/trends", testId: "nav-trends", icon: ChartLine },
] as const;

const TABS = [
  { key: "sessions", href: "/sessions", icon: LayoutList },
  { key: "practice", href: "/practice", icon: Dumbbell },
  { key: "trends", href: "/trends", icon: ChartLine },
  { key: "settings", href: "/settings", icon: Settings },
] as const;

function initials(email?: string | null) {
  const local = (email ?? "").split("@")[0] ?? "";
  const parts = local.split(/[._-]+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
  return (local.slice(0, 2) || "·").toUpperCase();
}

export function AppShell({ locale, email, role, children }: AppShellProps) {
  const t = useTranslations("nav");
  const signal = useTranslations("signal");
  const pathname = usePathname();
  const router = useRouter();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const { applied, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const toggle = useCallback(() => setOpen((value) => !value), []);
  useCommandShortcut(toggle);

  function active(href: string) {
    const path = `${prefix}${href}`;
    return pathname === path || pathname.startsWith(`${path}/`);
  }

  const actions: PaletteAction[] = [
    { id: "ask", label: signal("askCoach"), ai: true, hint: "AI", run: () => router.push(`${prefix}/practice`) },
    { id: "new", label: signal("actionNew"), run: () => router.push(`${prefix}/sessions/new`) },
    { id: "sessions", label: t("sessions"), run: () => router.push(`${prefix}/sessions`) },
    { id: "practice", label: t("practice"), run: () => router.push(`${prefix}/practice`) },
    { id: "prep", label: t("prep"), run: () => router.push(`${prefix}/prep`) },
    { id: "trends", label: t("trends"), run: () => router.push(`${prefix}/trends`) },
    { id: "research", label: t("research"), run: () => router.push(`${prefix}/research`) },
    { id: "settings", label: t("settings"), run: () => router.push(`${prefix}/settings`) },
    {
      id: "theme",
      label: signal("actionTheme"),
      run: () => setTheme(applied === "dark" ? "light" : "dark"),
    },
    {
      id: "locale",
      label: locale === "en" ? "Português" : "English",
      run: () => router.push(locale === "en" ? "/pt-BR/sessions" : "/sessions"),
    },
  ];
  if (role === "admin") {
    actions.push(
      { id: "admin", label: t("admin"), run: () => router.push(`${prefix}/admin/users`) },
      { id: "costs", label: signal("actionCosts"), run: () => router.push(`${prefix}/admin/costs`) },
    );
  }

  const skip = locale === "pt-BR" ? "Pular para o conteúdo" : "Skip to content";

  return (
    <div className="cs-app">
      <a href="#main" className="cs-skip">{skip}</a>
      <SessionWatch locale={locale} />
      <nav className="cs-rail" aria-label={signal("principal")}>
        <Link href={`${prefix}/sessions`} className="k-rail-mark k-keep" aria-label="CYBERSPHERE Stage Coach" data-testid="brand">
          <CompactMark />
        </Link>
        {RAIL.map((link) => {
          const Icon = link.icon;
          return (
            <Link
              key={link.key}
              href={`${prefix}${link.href}`}
              data-testid={link.testId}
              aria-current={active(link.href) ? "page" : undefined}
              aria-label={t(link.key)}
              title={t(link.key)}
            >
              <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
            </Link>
          );
        })}
        <button type="button" className="rail-item k-ai-item" aria-label={signal("askCoach")} title={signal("askCoach")} onClick={() => setOpen(true)}>
          <Sparkles className="h-[18px] w-[18px]" aria-hidden="true" />
        </button>
        <Link href={`${prefix}/settings`} data-testid="nav-settings" aria-current={active("/settings") ? "page" : undefined} aria-label={t("settings")} title={t("settings")}>
          <Settings className="h-[18px] w-[18px]" aria-hidden="true" />
        </Link>
        {role === "admin" ? (
          <Link href={`${prefix}/admin/users`} data-testid="nav-admin" aria-current={active("/admin/users") ? "page" : undefined} aria-label={t("admin")} title={t("admin")}>
            <Users className="h-[18px] w-[18px]" aria-hidden="true" />
          </Link>
        ) : null}
        <span className="k-rail-gap" />
        <span className="k-avatar" aria-label={signal("account")} title={signal("account")}>{initials(email)}</span>
      </nav>
      <div className="cs-app-main">
        <div className="k-app-head">
          <button type="button" className="k-cmd" data-testid="command-button" aria-label={signal("commandLabel")} onClick={() => setOpen(true)}>
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            <span style={{ flex: 1, textAlign: "left" }}>{signal("askOrSearch")}</span>
            <span className="cs-kbd">⌘K</span>
          </button>
        </div>
        <main id="main">{children}</main>
      </div>
      <nav className="k-tabbar" aria-label={signal("principal")}>
        {TABS.slice(0, 2).map((link) => {
          const Icon = link.icon;
          return (
            <Link key={link.key} href={`${prefix}${link.href}`} aria-current={active(link.href) ? "page" : undefined}>
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span>{t(link.key)}</span>
            </Link>
          );
        })}
        <button type="button" className="k-ai-item" onClick={() => setOpen(true)}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          <span>{signal("askShort")}</span>
        </button>
        {TABS.slice(2).map((link) => {
          const Icon = link.icon;
          return (
            <Link key={link.key} href={`${prefix}${link.href}`} aria-current={active(link.href) ? "page" : undefined}>
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span>{t(link.key)}</span>
            </Link>
          );
        })}
      </nav>
      {open ? <CommandPalette open onClose={() => setOpen(false)} actions={actions} /> : null}
    </div>
  );
}
