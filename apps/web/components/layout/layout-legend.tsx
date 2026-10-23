"use client";

import { useTranslations } from "next-intl";
import type { LayoutRole } from "@/lib/online";

export function LayoutLegend({ roles }: { roles: LayoutRole[] }) {
  const t = useTranslations("online");
  if (!roles.length) return null;
  return (
    <div>
      <p className="cs-eyebrow">{t("legendTitle")}</p>
      <ul className="mt-3 space-y-3">
        {roles.map((role) => {
          const key = role === "other_participant" ? "other" : role;
          const hatched = role === "ignore" || role === "other_participant";
          return (
            <li key={role} className="flex items-start gap-3">
              <span
                aria-hidden="true"
                className={`mt-1 h-[26px] w-10 shrink-0 border-2 border-current text-[color:var(--text-strong)] ${
                  key === "screen" ? "border-dashed" : hatched ? "border-dotted" : "border-solid"
                }`}
                style={
                  hatched
                    ? {
                        background: "repeating-linear-gradient(45deg, currentColor 0 1px, transparent 1px 6px)",
                      }
                    : undefined
                }
              />
              <span>
                <span className="block text-xs uppercase tracking-[0.08em]">{t(`chip.${key === "ignore" ? "ignored" : key}`)}</span>
                <span className="mt-1 block text-sm text-[color:var(--text-secondary)]">{t(`legend.${key}`)}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
