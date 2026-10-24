"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useLocale } from "next-intl";
import { signIn } from "next-auth/react";

const COPY = {
  en: {
    heading: "Sign in",
    intro: "Email and password, or Sign in with Apple.",
    email: "Email",
    password: "Password",
    submit: "Sign in",
    signingIn: "Signing in…",
    register: "Create account",
    forgot: "Forgot password",
    forgotSubmit: "Request reset",
    verify: "I have a verification token",
    token: "Token",
    verifySubmit: "Verify email",
    apple: "Sign in with Apple",
    appleOff: "Sign in with Apple is disabled until Apple secrets are configured.",
    invalid: "Invalid email or password.",
    limited: "Too many sign-in attempts. Wait a moment and try again.",
    error: "Could not complete that request.",
    signedIn: "Signed in.",
    registered: "Check the console email stand-in for a verification token.",
    verified: "Email verified. You can sign in.",
    resetSent: "Password resets are issued by an administrator. Ask an admin to set a temporary password.",
  },
  "pt-BR": {
    heading: "Entrar",
    intro: "E-mail e senha, ou Entrar com a Apple.",
    email: "E-mail",
    password: "Senha",
    submit: "Entrar",
    signingIn: "Entrando…",
    register: "Criar conta",
    forgot: "Esqueci a senha",
    forgotSubmit: "Pedir redefinição",
    verify: "Tenho um token de verificação",
    token: "Token",
    verifySubmit: "Verificar e-mail",
    apple: "Entrar com a Apple",
    appleOff: "Entrar com a Apple fica desligado até os segredos da Apple existirem.",
    invalid: "E-mail ou senha inválidos.",
    limited: "Muitas tentativas de entrada. Espere um instante e tente de novo.",
    error: "Não foi possível concluir o pedido.",
    signedIn: "Sessão iniciada.",
    registered: "Veja o stand-in de e-mail no console para o token de verificação.",
    verified: "E-mail verificado. Pode entrar.",
    resetSent: "A redefinição de senha é feita por um administrador. Peça uma senha temporária.",
  },
} as const;

type Mode = "login" | "register" | "forgot" | "verify";
type Phase = "empty" | "loading" | "error" | "success";

export function SignInForm() {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const [mode, setMode] = useState<Mode>("login");
  const [phase, setPhase] = useState<Phase>("empty");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [appleEnabled, setAppleEnabled] = useState(false);

  useEffect(() => {
    void fetch("/api/stagecoach/auth/apple/config", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as { enabled?: boolean };
        setAppleEnabled(Boolean(body.enabled));
      })
      .catch(() => undefined);
  }, []);

  function switchMode(next: Mode) {
    setMode(next);
    setPhase("empty");
    setError("");
    setNotice("");
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPhase("loading");
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");
    const token = String(form.get("token") || "");
    const prefix = locale === "pt-BR" ? "/pt-BR" : "";
    try {
      if (mode === "login") {
        const check = await fetch("/api/stagecoach/auth/login", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const body = (await check.json().catch(() => null)) as {
          session_ticket?: string;
          must_change_password?: boolean;
        } | null;
        if (!check.ok) {
          setPhase("error");
          setError(check.status === 429 ? t.limited : t.invalid);
          return;
        }
        setPhase("success");
        setNotice(t.signedIn);
        const result = await signIn("credentials", { ticket: body?.session_ticket, redirect: false });
        if (result?.error) {
          setPhase("error");
          setError(t.error);
          return;
        }
        const next = body?.must_change_password ? `${prefix}/account/password` : `${prefix}/sessions`;
        window.location.assign(next);
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
        setPhase("success");
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
        setPhase("success");
        return;
      }
      const response = await fetch("/api/stagecoach/auth/verify-email", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!response.ok) throw new Error(t.error);
      setNotice(t.verified);
      setPhase("success");
      setMode("login");
    } catch (reason) {
      setPhase("error");
      setError(reason instanceof Error ? reason.message : t.error);
    }
  }

  async function startApple() {
    setError("");
    const redirect = `${window.location.origin}${locale === "pt-BR" ? "/pt-BR" : ""}/auth/apple/callback`;
    const response = await fetch("/api/stagecoach/auth/apple/start", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ redirect_uri: redirect }),
    });
    if (!response.ok) {
      setPhase("error");
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

  const submitLabel =
    phase === "loading" && mode === "login"
      ? t.signingIn
      : mode === "login"
        ? t.submit
        : mode === "register"
          ? t.register
          : mode === "forgot"
            ? t.forgotSubmit
            : t.verifySubmit;

  return (
    <div
      className="mx-auto w-full min-w-0 max-w-md space-y-6 border bg-card p-6"
      data-testid="sign-in-form"
      data-state={phase}
      aria-busy={phase === "loading"}
    >
      <div>
        <h1 className="text-2xl">{t.heading}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t.intro}</p>
      </div>
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-3">
        {mode !== "verify" ? (
          <label className="block text-sm font-medium">
            {t.email}
            <input
              name="email"
              type="email"
              required
              autoComplete="username"
              className="mt-1 w-full px-3 py-2"
              data-testid="auth-email"
            />
          </label>
        ) : null}
        {mode === "login" || mode === "register" ? (
          <label className="block text-sm font-medium">
            {t.password}
            <input
              name="password"
              type="password"
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 10 : undefined}
              className="mt-1 w-full px-3 py-2"
              data-testid="auth-password"
            />
          </label>
        ) : null}
        {mode === "verify" ? (
          <label className="block text-sm font-medium">
            {t.token}
            <input name="token" required className="mt-1 w-full px-3 py-2" data-testid="auth-token" />
          </label>
        ) : null}
        <button
          type="submit"
          disabled={phase === "loading"}
          data-testid="auth-submit"
          className="w-full bg-primary px-3 py-2 text-sm text-primary-foreground"
        >
          {submitLabel}
        </button>
      </form>
      {appleEnabled ? (
        <button
          type="button"
          data-testid="apple-signin"
          onClick={() => void startApple()}
          className="w-full border px-3 py-2 text-sm"
        >
          {t.apple}
        </button>
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="apple-disabled">
          {t.appleOff}
        </p>
      )}
      <div className="flex min-w-0 flex-wrap gap-3 text-sm">
        <button type="button" className="underline" onClick={() => switchMode("login")}>
          {t.submit}
        </button>
        <button type="button" className="underline" data-testid="auth-register" onClick={() => switchMode("register")}>
          {t.register}
        </button>
        <button type="button" className="underline" onClick={() => switchMode("forgot")}>
          {t.forgot}
        </button>
        <button type="button" className="underline" onClick={() => switchMode("verify")}>
          {t.verify}
        </button>
      </div>
      {notice ? (
        <p className="text-sm" data-testid="auth-success">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" data-testid="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
