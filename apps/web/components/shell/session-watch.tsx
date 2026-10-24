"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";

export function SessionWatch({ locale }: { locale: string }) {
  const router = useRouter();
  useEffect(() => {
    let cancelled = false;
    const prefix = locale === "en" ? "" : `/${locale}`;
    void fetch("/api/stagecoach/me", { cache: "no-store" })
      .then(async (response) => {
        if (cancelled) return;
        if (response.status === 401) {
          await signOut({ callbackUrl: `${prefix}/sign-in` });
          return;
        }
        if (response.status !== 403) return;
        const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        if (body?.detail === "Password change required") {
          router.push(`${prefix}/account/password`);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [locale, router]);
  return null;
}
