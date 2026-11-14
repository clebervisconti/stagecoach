"use client";

import { useEffect, useSyncExternalStore } from "react";

export type ThemeChoice = "system" | "light" | "dark";

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.addEventListener("storage", onChange);
  return () => {
    observer.disconnect();
    window.removeEventListener("storage", onChange);
  };
}

function choiceSnapshot(): ThemeChoice {
  const saved = localStorage.getItem("cs-theme");
  return saved === "light" || saved === "dark" ? saved : "system";
}

function appliedSnapshot(): "light" | "dark" {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function useTheme() {
  const choice = useSyncExternalStore(subscribe, choiceSnapshot, () => "system" as ThemeChoice);
  const applied = useSyncExternalStore(subscribe, appliedSnapshot, () => "dark" as const);

  function setTheme(next: ThemeChoice) {
    if (next === "system") {
      localStorage.removeItem("cs-theme");
      const os = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
      document.documentElement.dataset.theme = os;
    } else {
      localStorage.setItem("cs-theme", next);
      document.documentElement.dataset.theme = next;
    }
    window.dispatchEvent(new Event("storage"));
  }

  return { choice, applied, setTheme };
}

export function ThemeSync() {
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const apply = () => {
      if (localStorage.getItem("cs-theme")) return;
      document.documentElement.dataset.theme = media.matches ? "light" : "dark";
    };
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);
  return null;
}
