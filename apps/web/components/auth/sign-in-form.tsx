"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useLocale } from "next-intl";
import { signIn } from "next-auth/react";

const COPY = {
  en: {
    heading: "Sign in",
    intro: "Email and password, or Sign in with Apple. Magic links are retired.",
    email: "Email",
    password: "Password",
    submit: "Sign in",
    register: "Create account",
    forgot: "Send reset email",
    verify: "I have a verification token",
    token: "Token",
    verifySubmit: "Verify email",
    resetSubmit: "Set new password",
    apple: "Sign in with Apple",
    appleOff: "Sign in with Apple is disabled until Apple secrets are configured.",
    error: "Could not complete that request.",
    registered: "Check the console email stand-in for a verification token.",
    verified: "Email verified. You can sign in.",
    resetSent: "If that account exists, a reset token is in the console email stand-in.",
    resetDone: "Password updated. You can sign in.",
  },
  "pt-BR": {
    heading: "Entrar",
    intro: "E-mail e senha, ou Entrar com a Apple. Links mágicos foram descontinuados.",
    email: "E-mail",
    password: "Senha",
    submit: "Entrar",
    register: "Criar conta",
    forgot: "Enviar e-mail de redefinição",
    verify: "Tenho um token de verificação",
    token: "Token",
    verifySubmit: "Verificar e-mail",
    resetSubmit: "Definir nova senha",
    apple: "Entrar com a Apple",
    appleOff: "Entrar com a Apple fica desligado até os segredos da Apple existirem.",
    error: "Não foi possível concluir o pedido.",
    registered: "Veja o stand-in de e-mail no console para o token de verificação.",
    verified: "E-mail verificado. Pode entrar.",
    resetSent: "Se a conta existir, o token de redefinição está no stand-in de e-mail.",
    resetDone: "Senha atualizada. Pode entrar.",
  },
} as const;

export function SignInForm() {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const [mode, setMode] = useState<"login" | "register" | "forgot" | "verify" | "reset">("login");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [appleEnabled, setAppleEnabled] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void fetch("/api/stagecoach/auth/apple/config", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as { enabled?: boolean };
        setAppleEnabled(Boolean(body.enabled));
      })
      .catch(() => undefined);
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");
    const token = String(form.get("token") || "");
    try {
      if (mode === "login") {
        const check = await fetch("/api/stagecoach/auth/login", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!check.ok) throw new Error(t.error);
        await signIn("credentials", { email, password, callbackUrl: "/sessions" });
        return;
      }
      if (mode === "register") {
        const response = await fetch("/api/stagecoach/auth/register", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!response.ok) throw new Error(t.error);
        setNotice(t.registered);
        return;
      }
      if (mode === "forgot") {
        const response = await fetch("/api/stagecoach/auth/forgot", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ email }),
        });
        if (!response.ok) throw new Error(t.error);
        setNotice(t.resetSent);
        setMode("reset");
        return;
      }
      if (mode === "verify") {
        const response = await fetch("/api/stagecoach/auth/verify-email", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (!response.ok) throw new Error(t.error);
        setNotice(t.verified);
        setMode("login");
        return;
      }
      const response = await fetch("/api/stagecoach/auth/reset", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      if (!response.ok) throw new Error(t.error);
      setNotice(t.resetDone);
      setMode("login");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t.error);
    } finally {
      setBusy(false);
    }
  }

  async function startApple() {
    setError("");
    const redirect = `${window.location.origin}/auth/apple/callback`;
    const response = await fetch("/api/stagecoach/auth/apple/start", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ redirect_uri: redirect }),
    });
    if (!response.ok) {
      setError(t.appleOff);
      return;
    }
    const body = (await response.json()) as {
      authorize_url: string;
      verifier: string;
      nonce: string;
      state: string;
    };
    sessionStorage.setItem(
      "apple-oidc",
      JSON.stringify({ verifier: body.verifier, nonce: body.nonce, state: body.state, redirect }),
    );
    window.location.assign(body.authorize_url);
  }

  return (
    <div className="mx-auto w-full max-w-md space-y-6 rounded-lg border bg-card p-6" data-testid="sign-in-form">
      <div>
        <h1 className="text-2xl font-bold">{t.heading}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t.intro}</p>
      </div>
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-3">
        {mode !== "verify" && mode !== "reset" ? (
          <label className="block text-sm font-medium">
            {t.email}
            <input
              name="email"
              type="email"
              required
              className="mt-1 w-full rounded-md border px-3 py-2"
              data-testid="auth-email"
            />
          </label>
        ) : null}
        {mode === "login" || mode === "register" || mode === "reset" ? (
          <label className="block text-sm font-medium">
            {t.password}
            <input
              name="password"
              type="password"
              required
              minLength={10}
              className="mt-1 w-full rounded-md border px-3 py-2"
              data-testid="auth-password"
            />
          </label>
        ) : null}
        {mode === "verify" || mode === "reset" ? (
          <label className="block text-sm font-medium">
            {t.token}
            <input name="token" required className="mt-1 w-full rounded-md border px-3 py-2" data-testid="auth-token" />
          </label>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          data-testid="auth-submit"
          className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
        >
          {mode === "login"
            ? t.submit
            : mode === "register"
              ? t.register
              : mode === "forgot"
                ? t.forgot
                : mode === "verify"
                  ? t.verifySubmit
                  : t.resetSubmit}
        </button>
      </form>
      {appleEnabled ? (
        <button
          type="button"
          data-testid="apple-signin"
          onClick={() => void startApple()}
          className="w-full rounded-md border px-3 py-2 text-sm"
        >
          {t.apple}
        </button>
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="apple-disabled">
          {t.appleOff}
        </p>
      )}
      <div className="flex flex-wrap gap-3 text-sm">
        <button type="button" className="underline" onClick={() => setMode("login")}>
          {t.submit}
        </button>
        <button type="button" className="underline" data-testid="auth-register" onClick={() => setMode("register")}>
          {t.register}
        </button>
        <button type="button" className="underline" onClick={() => setMode("forgot")}>
          {t.forgot}
        </button>
        <button type="button" className="underline" onClick={() => setMode("verify")}>
          {t.verify}
        </button>
      </div>
      {notice ? <p className="text-sm">{notice}</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
