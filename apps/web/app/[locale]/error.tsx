"use client";

import { AuthFrame } from "@/components/auth/auth-frame";
import { Button } from "@/components/ui/button";

export default function LocaleError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <AuthFrame>
      <h1 className="text-3xl">Something went wrong</h1>
      <p className="mt-3 text-base leading-[26px] text-[color:var(--text-secondary)]">The page could not be loaded.</p>
      <Button type="button" className="mt-8" onClick={() => reset()}>
        Try again
      </Button>
    </AuthFrame>
  );
}
