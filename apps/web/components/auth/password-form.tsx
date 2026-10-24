"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { signIn, signOut } from "next-auth/react";

const COPY = {
  en: {
    heading: "Change password",
    forced: "Choose a new password before continuing. Nothing else is available until you do.",
    hint: "At least 10 characters, and not a common breached password.",
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
    hint: "No mínimo 10 caracteres, e não uma senha comum de vazamentos.",
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
    <div
      className="mx-auto w-full min-w-0 max-w-md space-y-6 border bg-card p-6"
      data-testid="password-change"
      data-state={phase}
      aria-busy={phase === "loading"}
    >
      <div>
        <h1 className="text-2xl">{t.heading}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{forced ? t.forced : t.hint}</p>
        {forced ? <p className="mt-2 text-sm text-muted-foreground">{t.hint}</p> : null}
      </div>
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-3">
        <label className="block text-sm font-medium">
          {t.current}
          <input
            name="current"
            type="password"
            autoComplete="current-password"
            className="mt-1 w-full px-3 py-2"
            data-testid="password-current"
          />
        </label>
        <label className="block text-sm font-medium">
          {t.next}
          <input
            name="next"
            type="password"
            required
            minLength={10}
            autoComplete="new-password"
            className="mt-1 w-full px-3 py-2"
            data-testid="password-new"
          />
        </label>
        <label className="block text-sm font-medium">
          {t.confirm}
          <input
            name="confirm"
            type="password"
            required
            minLength={10}
            autoComplete="new-password"
            className="mt-1 w-full px-3 py-2"
            data-testid="password-confirm"
          />
        </label>
        <button
          type="submit"
          disabled={phase === "loading"}
          data-testid="password-submit"
          className="w-full bg-primary px-3 py-2 text-sm text-primary-foreground"
        >
          {phase === "loading" ? t.saving : t.submit}
        </button>
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
          <Link href={`${prefix}/sessions`} className="underline">
            {t.back}
          </Link>
        )}
        <button
          type="button"
          className="underline"
          onClick={() => void signOut({ callbackUrl: `${prefix}/sign-in` })}
        >
          {t.signOut}
        </button>
      </div>
    </div>
  );
}
