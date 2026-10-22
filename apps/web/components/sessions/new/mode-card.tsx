import { Globe, Mic, Play, Users } from "lucide-react";
import type { DeliveryMode } from "@/lib/online";
import { ModePictogram } from "@/components/sessions/pictograms/mode-pictogram";

const ICONS = {
  stage: Mic,
  webinar: Users,
  online_talk: Globe,
  recorded_video: Play,
} as const;

export function ModeCard({
  mode,
  title,
  description,
  coach,
  selected,
  tabIndex,
  describedBy,
  onSelect,
  onActivate,
}: {
  mode: DeliveryMode;
  title: string;
  description: string;
  coach: string;
  selected: boolean;
  tabIndex: number;
  describedBy: string;
  onSelect: () => void;
  onActivate: () => void;
}) {
  const Icon = ICONS[mode];
  return (
    <div
      role="radio"
      aria-checked={selected}
      aria-describedby={describedBy}
      tabIndex={tabIndex}
      data-testid={`mode-${mode}`}
      onClick={onSelect}
      onDoubleClick={onActivate}
      onKeyDown={(event) => {
        if (event.key === " " || event.key === "Spacebar") {
          event.preventDefault();
          onSelect();
        }
        if (event.key === "Enter" && selected) {
          event.preventDefault();
          onActivate();
        }
      }}
      className={`flex min-h-[72px] cursor-pointer flex-row items-start gap-3 rounded-[var(--radius-sm)] border bg-[color:var(--bg-subtle)] p-4 transition-colors duration-100 md:min-h-[300px] md:flex-col md:p-6 ${
        selected
          ? "border-[color:var(--text-strong)] bg-[color:var(--bg-muted)]"
          : "border-[color:var(--line)] hover:bg-[color:var(--bg-muted)]"
      } active:bg-[color:var(--bg-emphasis)]`}
    >
      <div className="flex w-full items-start justify-between gap-3">
        <ModePictogram mode={mode} className="h-10 w-16 text-[color:var(--text-secondary)] md:h-[70px] md:w-[112px]" />
        <span
          aria-hidden="true"
          className={`mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
            selected
              ? "border-[color:var(--text-strong)] bg-[color:var(--text-strong)]"
              : "border-[color:var(--line-strong)]"
          }`}
        >
          {selected ? <span className="h-2 w-2 rounded-full bg-[color:var(--bg)]" /> : null}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 shrink-0 md:h-5 md:w-5" aria-hidden="true" />
          <p className="font-display text-base font-bold uppercase tracking-[0.06em] text-[color:var(--text-strong)] md:text-lg md:leading-6">
            {title}
          </p>
        </div>
        <p id={describedBy} className="mt-2 text-sm text-[color:var(--text-secondary)]">
          {description}
        </p>
        <div className="mt-auto hidden md:block">
          <div className="mt-6 border-t border-[color:var(--line-subtle)] pt-3">
            <p className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-tertiary)]">We coach</p>
            <p className="mt-1 text-sm text-[color:var(--text-secondary)]">{coach}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
