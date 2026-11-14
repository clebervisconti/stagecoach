"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Sparkles } from "lucide-react";

export type PaletteAction = {
  id: string;
  label: string;
  hint?: string;
  ai?: boolean;
  run: () => void;
};

export function CommandPalette({
  open,
  onClose,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  actions: PaletteAction[];
}) {
  const t = useTranslations("signal");
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);

  const items = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return actions;
    return actions.filter((action) => action.label.toLowerCase().includes(needle));
  }, [actions, query]);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => inputRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [open]);

  if (!open) return null;

  function close() {
    onClose();
    setQuery("");
    window.requestAnimationFrame(() => restoreRef.current?.focus());
  }

  function choose(next: number) {
    const action = items[next];
    if (!action) return;
    close();
    action.run();
  }

  return (
    <div className="cs-cmdk-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
      <div className="cs-cmdk" role="dialog" aria-modal="true" aria-labelledby={titleId} data-testid="command-palette">
        <h2 id={titleId} className="cs-sr-only">{t("paletteLabel")}</h2>
        <div className="cs-cmdk-input">
          <input
            ref={inputRef}
            value={query}
            placeholder={t("askOrSearch")}
            aria-label={t("paletteLabel")}
            onChange={(event) => {
              setQuery(event.target.value);
              setIndex(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                close();
              } else if (event.key === "ArrowDown") {
                event.preventDefault();
                setIndex((value) => (items.length ? (value + 1) % items.length : 0));
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setIndex((value) => (items.length ? (value - 1 + items.length) % items.length : 0));
              } else if (event.key === "Enter") {
                event.preventDefault();
                choose(index);
              }
            }}
          />
          <span className="cs-kbd">esc</span>
        </div>
        <div className="cs-cmdk-list" role="listbox" aria-label={t("paletteLabel")}>
          {items.length === 0 ? <p className="k-note" style={{ padding: 12 }}>{t("noMatches")}</p> : null}
          {items.map((action, itemIndex) => (
            <button
              key={action.id}
              type="button"
              role="option"
              aria-selected={itemIndex === index}
              className={action.ai ? "cs-cmdk-item k-ai-item" : "cs-cmdk-item"}
              onMouseEnter={() => setIndex(itemIndex)}
              onClick={() => choose(itemIndex)}
            >
              <span className="k-row" style={{ gap: 8 }}>
                {action.ai ? <Sparkles className="h-4 w-4" aria-hidden="true" /> : null}
                <span>{action.label}</span>
                {action.ai ? <span className="cs-tag-ai">{t("ai")}</span> : null}
              </span>
              {action.hint ? <span className="cs-kbd">{action.hint}</span> : null}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function useCommandShortcut(onToggle: () => void) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onToggle();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onToggle]);
}
