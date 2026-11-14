"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useTheme, type ThemeChoice } from "@/components/shell/use-theme";

export function AppearancePanel() {
  const t = useTranslations("signal");
  const locale = useLocale();
  const { choice, setTheme } = useTheme();
  const options: { id: ThemeChoice; label: string }[] = [
    { id: "system", label: t("themeSystem") },
    { id: "dark", label: t("themeDark") },
    { id: "light", label: t("themeLight") },
  ];

  return (
    <section className="cs-panel" aria-labelledby="appearance-heading">
      <h2 id="appearance-heading" className="cs-panel-title">{t("appearance")}</h2>
      <div className="s-set-row">
        <div>
          <p className="font-medium">{t("theme")}</p>
          <p className="k-note">{t("themeHelp")}</p>
        </div>
        <div className="cs-tabs" role="radiogroup" aria-label={t("theme")} data-testid="theme-toggle">
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              role="radio"
              className="cs-tab"
              aria-checked={choice === option.id}
              onClick={() => setTheme(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      <div className="s-set-row">
        <div>
          <p className="font-medium">{t("language")}</p>
          <p className="k-note">{t("languageHelp")}</p>
        </div>
        <div className="k-row">
          <Link href="/settings" aria-current={locale === "en" ? "true" : undefined} className="cs-button cs-button-ghost">
            English
          </Link>
          <Link href="/pt-BR/settings" data-testid="locale-toggle" aria-current={locale === "pt-BR" ? "true" : undefined} className="cs-button cs-button-ghost">
            Português
          </Link>
        </div>
      </div>
      <div className="cs-alert cs-alert-neutral" role="note">
        <div className="cs-alert-body">
          <p className="cs-alert-title">{t("telemetryNote")}</p>
          <p>{t("telemetryBody")}</p>
        </div>
      </div>
    </section>
  );
}
