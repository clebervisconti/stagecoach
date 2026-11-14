"use client";

import { Button } from "@/components/ui/button";

export default function AppError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="px-6 py-10">
      <h1 className="text-3xl">Something went wrong</h1>
      <p className="mt-3 max-w-prose text-base leading-[26px] text-[color:var(--text-secondary)]">
        This page could not be loaded. Your session is still here.
      </p>
      <Button type="button" className="mt-8" onClick={() => reset()}>
        Try again
      </Button>
    </div>
  );
}
