"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale } from "next-intl";
import { signIn } from "next-auth/react";
import { AuthFrame } from "@/components/auth/auth-frame";
import { APPLE_CALLBACK_COPY, appleFailureKey, planAppleCallback, type AppleCallbackKey } from "@/lib/apple-callback";

export default function AppleCallbackPage() {
  const locale = useLocale();
  const t = APPLE_CALLBACK_COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const prefix = locale === "pt-BR" ? "/pt-BR" : "";
  const [key, setKey] = useState<AppleCallbackKey | "working">("working");

  useEffect(() => {
    const plan = planAppleCallback(window.location.search, sessionStorage.getItem("apple-oidc"));
    if (plan.type === "error") {
      sessionStorage.removeItem("apple-oidc");
      const next = plan.key;
      const timer = window.setTimeout(() => setKey(next), 0);
      return () => window.clearTimeout(timer);
    }
    let cancelled = false;
    void fetch("/api/stagecoach/auth/apple/finish", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(plan.body),
    })
      .then(async (response) => {
        const body = (await response.json().catch(() => null)) as {
          session_ticket?: string;
          must_change_password?: boolean;
          detail?: string;
        } | null;
        if (!response.ok) {
          throw new Error(appleFailureKey(response.status, typeof body?.detail === "string" ? body.detail : ""));
        }
        const result = await signIn("credentials", { ticket: body?.session_ticket, redirect: false });
        if (result?.error) throw new Error("failed");
        if (cancelled) return;
        sessionStorage.removeItem("apple-oidc");
        const next = body?.must_change_password ? `${prefix}/account/password` : `${prefix}/sessions`;
        window.location.assign(next);
      })
      .catch((reason: unknown) => {
        sessionStorage.removeItem("apple-oidc");
        if (cancelled) return;
        const value = reason instanceof Error ? reason.message : "failed";
        const known: AppleCallbackKey[] = ["cancelled", "unavailable", "startAgain", "noAccount", "invalidInvite", "failed"];
        setKey(known.includes(value as AppleCallbackKey) ? (value as AppleCallbackKey) : "failed");
      });
    return () => {
      cancelled = true;
    };
  }, [prefix]);

  return (
    <AuthFrame>
      <div data-testid="apple-callback" data-state={key}>
        <h1 className="text-3xl">{key === "working" ? t.working : t[key]}</h1>
        {key !== "working" ? (
          <p className="mt-6">
            <Link href={`${prefix}/sign-in`} className="cs-text-link">
              {t.back}
            </Link>
          </p>
        ) : null}
      </div>
    </AuthFrame>
  );
}
