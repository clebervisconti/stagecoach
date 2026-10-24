"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { signIn } from "next-auth/react";

export default function AppleCallbackPage() {
  const locale = useLocale();
  const [error, setError] = useState("");

  useEffect(() => {
    const prefix = locale === "pt-BR" ? "/pt-BR" : "";
    void Promise.resolve()
      .then(async () => {
        const params = new URLSearchParams(window.location.search);
        const stored = sessionStorage.getItem("apple-oidc");
        if (!stored) throw new Error("Missing Apple PKCE state");
        const parsed = JSON.parse(stored) as {
          verifier: string;
          nonce: string;
          redirect: string;
        };
        const response = await fetch("/api/stagecoach/auth/apple/finish", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            code: params.get("code"),
            nonce: parsed.nonce,
            verifier: parsed.verifier,
            redirect_uri: parsed.redirect,
            id_token: params.get("id_token") || undefined,
          }),
        });
        const body = (await response.json()) as {
          email?: string;
          session_ticket?: string;
          must_change_password?: boolean;
          detail?: string;
        };
        if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Apple sign-in failed");
        const result = await signIn("credentials", { ticket: body.session_ticket, redirect: false });
        if (result?.error) throw new Error("Apple sign-in failed");
        const next = body.must_change_password ? `${prefix}/account/password` : `${prefix}/sessions`;
        window.location.assign(next);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [locale]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4" data-testid="apple-callback">
      <p className="text-sm text-muted-foreground">{error || "Finishing Sign in with Apple…"}</p>
    </div>
  );
}
