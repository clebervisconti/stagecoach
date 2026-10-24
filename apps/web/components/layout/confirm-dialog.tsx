"use client";

import { useEffect, useRef } from "react";

export function ConfirmDialog({
  title,
  body,
  actions,
  onCancel,
}: {
  title: string;
  body: string;
  actions: { id: string; label: string; onClick: () => void; tone?: "primary" | "danger" | "ghost" }[];
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = ref.current;
    const buttons = root ? [...root.querySelectorAll<HTMLButtonElement>("button")] : [];
    buttons[0]?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onCancel();
        return;
      }
      if (event.key !== "Tab" || !buttons.length) return;
      const first = buttons[0];
      const last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center">
      <div
        ref={ref}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="layout-confirm-title"
        aria-describedby="layout-confirm-body"
        className="w-full max-w-md border border-[color:var(--line-strong)] bg-[color:var(--bg)] p-5"
      >
        <h2 id="layout-confirm-title" className="text-lg font-semibold">
          {title}
        </h2>
        <p id="layout-confirm-body" className="mt-2 text-sm text-[color:var(--text-secondary)]">
          {body}
        </p>
        <div className="mt-5 flex flex-col gap-2">
          {actions.map((action) => (
            <button
              key={action.id}
              type="button"
              data-testid={`confirm-${action.id}`}
              onClick={action.onClick}
              className={`inline-flex h-11 items-center justify-center rounded-[var(--radius-sm)] px-4 text-xs uppercase tracking-[0.08em] ${
                action.tone === "ghost"
                  ? "border border-[color:var(--line-strong)]"
                  : action.tone === "danger"
                    ? "bg-[color:var(--status-critical)] text-white"
                    : "bg-[color:var(--action-primary)] text-[color:var(--text-inverse)]"
              }`}
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
