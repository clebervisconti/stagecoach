"use client";

import { useTranslations } from "next-intl";
import type { EditorRole } from "@/lib/layout-edit";
import { roleKey } from "@/lib/layout-edit";

const ROLES: EditorRole[] = ["camera", "screen", "other_participant", "ignore"];

export function RoleControl({
  value,
  disabled,
  onChange,
  className = "",
  withTestIds = true,
}: {
  value: string | null;
  disabled?: boolean;
  onChange: (role: EditorRole) => void;
  className?: string;
  withTestIds?: boolean;
}) {
  const t = useTranslations("online");
  return (
    <div role="radiogroup" aria-label={t("layout.roles")} className={`grid grid-cols-4 gap-1 ${className}`}>
      {ROLES.map((role) => {
        const key = roleKey(role);
        const on = value === role;
        return (
          <button
            key={role}
            type="button"
            role="radio"
            aria-checked={on}
            disabled={disabled}
            data-testid={withTestIds ? `role-${key}` : undefined}
            onClick={() => onChange(role)}
            className={`h-9 min-w-0 truncate px-1 text-[11px] uppercase tracking-[0.06em] disabled:opacity-40 ${
              on
                ? "bg-[color:var(--bg-inverse)] text-[color:var(--text-inverse)]"
                : "border border-[color:var(--line-strong)]"
            }`}
          >
            {t(`layout.role.${key}`)}
          </button>
        );
      })}
    </div>
  );
}
