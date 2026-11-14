"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useLocale } from "next-intl";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordField } from "@/components/auth/password-field";

const COPY = {
  en: {
    login: "Sign in",
    register: "Create your account",
    forgot: "Reset your password",
    loginIntro: "Use the email and password for your account.",
    registerIntro: "Choose a password for the invited email address.",
    inviteOnly: "Ask an administrator for an invite.",
    forgotIntro: "Password resets are issued by an administrator.",
    email: "Email",
    password: "Password",
    submit: "Sign in",
    signingIn: "Signing in…",
    registerSubmit: "Create account",
    forgotSubmit: "Request reset",
    createLink: "Create an account",
    forgotLink: "Forgot password?",
    back: "Back to sign in",
    tokenLink: "I have a verification token",
    apple: "Sign in with Apple",
    invalid: "Invalid email or password.",
    limited: "Too many sign-in attempts. Wait a moment and try again.",
    error: "Could not complete that request.",
    appleFailed: "Sign in with Apple could not be completed.",
    signedIn: "Signed in.",
    registered: "Check your inbox for a link to confirm your email.",
    resetSent: "Password resets are issued by an administrator. Ask an admin to set a temporary password.",
    account: "Account",
  },
  "pt-BR": {
    login: "Entrar",
    register: "Crie sua conta",
    forgot: "Redefina sua senha",
    loginIntro: "Use o e-mail e a senha da sua conta.",
    registerIntro: "Escolha uma senha para o e-mail do convite.",
    inviteOnly: "Peça um convite a um administrador.",
    forgotIntro: "A redefinição de senha é feita por um administrador.",
    email: "E-mail",
    password: "Senha",
    submit: "Entrar",
    signingIn: "Entrando…",
    registerSubmit: "Criar conta",
    forgotSubmit: "Pedir redefinição",
    createLink: "Criar uma conta",
    forgotLink: "Esqueceu a senha?",
    back: "Voltar para entrar",
    tokenLink: "Tenho um token de verificação",
    apple: "Entrar com a Apple",
    invalid: "E-mail ou senha inválidos.",
    limited: "Muitas tentativas de entrada. Espere um instante e tente de novo.",
    error: "Não foi possível concluir o pedido.",
    appleFailed: "Não foi possível concluir a entrada com a Apple.",
    signedIn: "Sessão iniciada.",
    registered: "Veja sua caixa de entrada. Enviamos um link para confirmar o e-mail.",
    resetSent: "A redefinição de senha é feita por um administrador. Peça uma senha temporária.",
    account: "Conta",
  },
} as const;

type Mode = "login" | "register" | "forgot";
type Phase = "empty" | "loading" | "error" | "success";

function modeFrom(value: string | null, invite: string): Mode {
  if (value === "register" && invite) return "register";
  if (value === "forgot") return "forgot";
  if (value === "register") return "register";
  return "login";
}

export function SignInForm() {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const invite = search.get("invite")?.trim() ?? "";
  const mode = modeFrom(search.get("mode"), invite);
  const [phase, setPhase] = useState<Phase>("empty");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [appleEnabled, setAppleEnabled] = useState(false);
  const prefix = locale === "pt-BR" ? "/pt-BR" : "";

  useEffect(() => {
    void fetch("/api/stagecoach/auth/apple/config", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as { enabled?: boolean };
        setAppleEnabled(Boolean(body.enabled));
      })
      .catch(() => undefined);
  }, []);

  function hrefFor(next: Mode) {
    const params = new URLSearchParams(search.toString());
    if (next === "login") params.delete("mode");
    else params.set("mode", next);
    if (!invite) params.delete("invite");
    const query = params.toString();
    return query ? `${pathname}?${query}` : pathname;
  }

  function switchMode(next: Mode) {
    setPhase("empty");
    setError("");
    setNotice("");
    router.push(hrefFor(next));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPhase("loading");
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");
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
          body: JSON.stringify({ email, password, invite }),
        });
        if (!response.ok) throw new Error(t.error);
        setNotice(t.registered);
        setPhase("success");
        return;
      }
      const response = await fetch("/api/stagecoach/auth/forgot", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!response.ok) throw new Error(t.error);
      setNotice(t.resetSent);
      setPhase("success");
    } catch (reason) {
      setPhase("error");
      setError(reason instanceof Error ? reason.message : t.error);
    }
  }

  async function startApple() {
    setError("");
    const redirect = `${window.location.origin}${prefix}/auth/apple/callback`;
    const response = await fetch("/api/stagecoach/auth/apple/start", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ redirect_uri: redirect }),
    });
    if (!response.ok) {
      setPhase("error");
      setError(t.appleFailed);
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
      JSON.stringify({
        verifier: body.verifier,
        nonce: body.nonce,
        state: body.state,
        redirect,
        invite: invite || undefined,
      }),
    );
    window.location.assign(body.authorize_url);
  }

  const heading = mode === "register" ? t.register : mode === "forgot" ? t.forgot : t.login;
  const intro =
    mode === "register" ? (invite ? t.registerIntro : t.inviteOnly) : mode === "forgot" ? t.forgotIntro : t.loginIntro;
  const submitLabel =
    phase === "loading" && mode === "login"
      ? t.signingIn
      : mode === "register"
        ? t.registerSubmit
        : mode === "forgot"
          ? t.forgotSubmit
          : t.submit;
  const showForm = mode !== "register" || Boolean(invite);

  return (
    <div data-testid="sign-in-form" data-mode={mode} data-state={phase} aria-busy={phase === "loading"}>
      <h1 className="text-3xl">{heading}</h1>
      <p className="mt-3 text-base leading-[26px] text-[color:var(--text-secondary)]">{intro}</p>
      {showForm ? (
        <form onSubmit={(event) => void onSubmit(event)} className="mt-8 space-y-4">
          <Field label={t.email} htmlFor="auth-email">
            <Input id="auth-email" name="email" type="email" required autoComplete="username" data-testid="auth-email" />
          </Field>
          {mode !== "forgot" ? (
            <PasswordField
              name="password"
              label={t.password}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              testId="auth-password"
              required
              showRules={mode === "register"}
            />
          ) : null}
          <Button type="submit" disabled={phase === "loading"} data-testid="auth-submit" className="w-full">
            {submitLabel}
          </Button>
        </form>
      ) : null}
      {appleEnabled && (mode === "login" || (mode === "register" && Boolean(invite))) ? (
        <Button type="button" variant="ghost" data-testid="apple-signin" className="mt-3 w-full" onClick={() => void startApple()}>
          {t.apple}
        </Button>
      ) : null}
      <nav aria-label={t.account} className="mt-6 flex flex-col items-start gap-1">
        {mode !== "login" ? (
          <button type="button" className="cs-text-link" onClick={() => switchMode("login")}>
            {t.back}
          </button>
        ) : null}
        {invite && mode !== "register" ? (
          <button type="button" className="cs-text-link" data-testid="auth-register" onClick={() => switchMode("register")}>
            {t.createLink}
          </button>
        ) : null}
        {mode !== "forgot" ? (
          <button type="button" className="cs-text-link" onClick={() => switchMode("forgot")}>
            {t.forgotLink}
          </button>
        ) : null}
      </nav>
      <p className="mt-8">
        <Link href={`${prefix}/verify-request`} className="cs-text-link text-[color:var(--text-tertiary)]">
          {t.tokenLink}
        </Link>
      </p>
      {notice ? (
        <p className="mt-4 text-sm" data-testid="auth-success">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 text-sm text-destructive" data-testid="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
