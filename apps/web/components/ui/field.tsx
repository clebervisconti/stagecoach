import type { ReactNode } from "react";

export function Field({
  label,
  htmlFor,
  hint,
  hintId,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  hintId?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {hint ? (
        <p id={hintId} className="text-sm leading-5 text-[color:var(--text-tertiary)]">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
