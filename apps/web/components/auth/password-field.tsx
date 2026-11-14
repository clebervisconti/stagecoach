"use client";

import { useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useLocale } from "next-intl";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const COPY = {
  en: {
    show: "Show password",
    hide: "Hide password",
    rules: "At least 10 characters, at most 200, and not a commonly breached password.",
    short: "Use at least 10 characters.",
    long: "Use at most 200 characters.",
  },
  "pt-BR": {
    show: "Mostrar senha",
    hide: "Ocultar senha",
    rules: "No mínimo 10 caracteres, no máximo 200, e não uma senha comum de vazamentos.",
    short: "Use no mínimo 10 caracteres.",
    long: "Use no máximo 200 caracteres.",
  },
} as const;

export function PasswordField({
  name,
  label,
  autoComplete,
  testId,
  required = false,
  showRules = false,
}: {
  name: string;
  label: string;
  autoComplete: string;
  testId?: string;
  required?: boolean;
  showRules?: boolean;
}) {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const id = useId();
  const hintId = `${id}-hint`;
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState("");

  return (
    <Field label={label} htmlFor={id} hint={showRules ? t.rules : undefined} hintId={showRules ? hintId : undefined} error={error}>
      <div className="flex items-stretch gap-2">
        <Input
          id={id}
          name={name}
          type={visible ? "text" : "password"}
          required={required}
          autoComplete={autoComplete}
          minLength={showRules ? 10 : undefined}
          maxLength={showRules ? 200 : undefined}
          aria-describedby={showRules ? hintId : undefined}
          data-testid={testId}
          className="min-w-0 flex-1"
          onBlur={(event) => {
            if (!showRules) return;
            const length = event.currentTarget.value.length;
            if (length > 0 && length < 10) setError(t.short);
            else if (length > 200) setError(t.long);
            else setError("");
          }}
        />
        <button
          type="button"
          className="cs-button cs-button-ghost w-11 shrink-0 px-0"
          aria-pressed={visible}
          aria-label={visible ? t.hide : t.show}
          onClick={() => setVisible((value) => !value)}
        >
          {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
    </Field>
  );
}
