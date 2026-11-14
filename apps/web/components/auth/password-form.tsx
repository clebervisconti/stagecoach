"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { signIn, signOut } from "next-auth/react";
import { AuthFrame } from "@/components/auth/auth-frame";
import { PasswordField } from "@/components/auth/password-field";
import { Button } from "@/components/ui/button";

const COPY = {
  en: {
    heading: "Change password",
    forced: "Choose a new password before continuing. Nothing else is available until you do.",
    hint: "At least 10 characters, at most 200, and not a commonly breached password.",
    current: "Current password",
    next: "New password",
    confirm: "Confirm new password",
    submit: "Update password",
    saving: "Saving…",
    success: "Password updated.",
    error: "Could not update the password.",
    mismatch: "Passwords do not match.",
    back: "Back to sessions",
    signOut: "Sign out",
  },
  "pt-BR": {
    heading: "Alterar senha",
    forced: "Escolha uma nova senha antes de continuar. Nada mais fica disponível até lá.",
    hint: "No mínimo 10 caracteres, no máximo 200, e não uma senha comum de vazamentos.",
    current: "Senha atual",
    next: "Nova senha",
    confirm: "Confirmar nova senha",
    submit: "Atualizar senha",
    saving: "Salvando…",
    success: "Senha atualizada.",
    error: "Não foi possível atualizar a senha.",
    mismatch: "As senhas não coincidem.",
    back: "Voltar às sessões",
    signOut: "Sair",
  },
} as const;

type Phase = "empty" | "loading" | "error" | "success";

export function PasswordForm({ forced }: { forced: boolean }) {
  const locale = useLocale();
  const router = useRouter();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const prefix = locale === "pt-BR" ? "/pt-BR" : "";
  const [phase, setPhase] = useState<Phase>("empty");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const current = String(form.get("current") || "");
    const next = String(form.get("next") || "");
    const confirm = String(form.get("confirm") || "");
    if (next !== confirm) {
      setPhase("error");
      setError(t.mismatch);
      return;
    }
    setPhase("loading");
    try {
      const response = await fetch("/api/stagecoach/auth/password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          current_password: current,
          new_password: next,
          confirm_password: confirm,
        }),
      });
      const body = (await response.json().catch(() => null)) as {
        detail?: string;
        session_ticket?: string;
      } | null;
      if (!response.ok) {
        setPhase("error");
        setError(typeof body?.detail === "string" ? body.detail : t.error);
        return;
      }
      setPhase("success");
      setNotice(t.success);
      const result = await signIn("credentials", { ticket: body?.session_ticket, redirect: false });
      if (result?.error) {
        setPhase("error");
        setError(t.error);
        return;
      }
      router.refresh();
      router.push(`${prefix}/sessions`);
    } catch (reason) {
      setPhase("error");
      setError(reason instanceof Error ? reason.message : t.error);
    }
  }

  return (
    <AuthFrame>
    <div
      data-testid="password-change"
      data-state={phase}
      aria-busy={phase === "loading"}
    >
      <div>
        <h1 className="text-3xl">{t.heading}</h1>
        <p className="mt-3 text-base leading-[26px] text-[color:var(--text-secondary)]">{forced ? t.forced : t.hint}</p>
        {forced ? <p className="mt-2 text-sm text-[color:var(--text-tertiary)]">{t.hint}</p> : null}
      </div>
      <form onSubmit={(event) => void onSubmit(event)} className="mt-8 space-y-4">
        <PasswordField
          name="current"
          label={t.current}
          autoComplete="current-password"
          testId="password-current"
        />
        <PasswordField
          name="next"
          label={t.next}
          autoComplete="new-password"
          testId="password-new"
          required
          showRules
        />
        <PasswordField
          name="confirm"
          label={t.confirm}
          autoComplete="new-password"
          testId="password-confirm"
          required
          showRules
        />
        <Button type="submit" disabled={phase === "loading"} data-testid="password-submit" className="w-full">
          {phase === "loading" ? t.saving : t.submit}
        </Button>
      </form>
      {notice ? (
        <p className="text-sm" data-testid="password-success">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" data-testid="password-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        {forced ? (
          <span />
        ) : (
          <Link href={`${prefix}/sessions`} className="cs-text-link">
            {t.back}
          </Link>
        )}
        <button
          type="button"
          className="cs-text-link"
          onClick={() => void signOut({ callbackUrl: `${prefix}/sign-in` })}
        >
          {t.signOut}
        </button>
      </div>
    </div>
    </AuthFrame>
  );
}
