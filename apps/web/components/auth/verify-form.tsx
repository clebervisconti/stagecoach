"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLocale } from "next-intl";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const COPY = {
  en: {
    heading: "Confirm your email",
    intro: "Paste the token from the confirmation email.",
    token: "Verification token",
    submit: "Verify email",
    working: "Verifying…",
    verified: "Email verified. You can sign in.",
    error: "Could not verify that token.",
    back: "Back to sign in",
  },
  "pt-BR": {
    heading: "Confirme seu e-mail",
    intro: "Cole o token que veio no e-mail de confirmação.",
    token: "Token de verificação",
    submit: "Verificar e-mail",
    working: "Verificando…",
    verified: "E-mail verificado. Você já pode entrar.",
    error: "Não foi possível verificar esse token.",
    back: "Voltar para entrar",
  },
} as const;

export function VerifyForm() {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const search = useSearchParams();
  const prefix = locale === "pt-BR" ? "/pt-BR" : "";
  const [phase, setPhase] = useState<"empty" | "loading" | "error" | "success">("empty");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPhase("loading");
    setError("");
    const token = String(new FormData(event.currentTarget).get("token") || "");
    try {
      const response = await fetch("/api/stagecoach/auth/verify-email", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!response.ok) throw new Error(t.error);
      setPhase("success");
    } catch (reason) {
      setPhase("error");
      setError(reason instanceof Error ? reason.message : t.error);
    }
  }

  return (
    <div data-testid="verify-form" data-state={phase}>
      <h1 className="text-3xl">{t.heading}</h1>
      <p className="mt-3 text-base leading-[26px] text-[color:var(--text-secondary)]">{t.intro}</p>
      <form onSubmit={(event) => void onSubmit(event)} className="mt-8 space-y-4">
        <Field label={t.token} htmlFor="auth-token">
          <Input
            id="auth-token"
            name="token"
            required
            defaultValue={search.get("token") ?? ""}
            autoComplete="one-time-code"
            data-testid="auth-token"
          />
        </Field>
        <Button type="submit" disabled={phase === "loading"} data-testid="auth-verify" className="w-full">
          {phase === "loading" ? t.working : t.submit}
        </Button>
      </form>
      {phase === "success" ? (
        <p className="mt-4 text-sm" data-testid="auth-success">
          {t.verified}
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <p className="mt-6">
        <Link href={`${prefix}/sign-in`} className="cs-text-link">
          {t.back}
        </Link>
      </p>
    </div>
  );
}
