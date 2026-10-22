import type { DeliveryMode } from "@/lib/online";

type StepId = "where" | "recording" | "layout";

export function WizardStepper({
  mode,
  current,
  layoutDone,
  onSelect,
}: {
  mode: DeliveryMode | null;
  current: StepId;
  layoutDone?: boolean;
  onSelect?: (step: StepId) => void;
}) {
  const online = mode !== null && mode !== "stage";
  const steps: { id: StepId; n: number; label: string; doneLabel?: string }[] = [
    { id: "where", n: 1, label: "Where" },
    { id: "recording", n: 2, label: "Recording" },
  ];
  if (online) {
    steps.push({
      id: "layout",
      n: 3,
      label: "Layout",
      doneLabel: layoutDone ? "Confirmed automatically" : undefined,
    });
  }
  const currentIndex = steps.findIndex((step) => step.id === current);
  return (
    <nav aria-label="Progress" className="mb-8">
      <ol className="flex flex-wrap items-center gap-4 text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-tertiary)]">
        {steps.map((step, index) => {
          const currentStep = step.id === current;
          const done = index < currentIndex || (step.id === "layout" && layoutDone);
          const clickable = Boolean(onSelect) && (done || currentStep);
          const label = done && step.doneLabel ? step.doneLabel : step.label;
          return (
            <li
              key={step.id}
              aria-current={currentStep ? "step" : undefined}
              className={currentStep ? "text-[color:var(--text-strong)]" : done ? "text-[color:var(--text)]" : ""}
            >
              {clickable ? (
                <button
                  type="button"
                  className="uppercase tracking-[0.12em]"
                  onClick={() => onSelect?.(step.id)}
                >
                  <span className="sr-only">{`Step ${step.n} of ${steps.length}, ${label}`}</span>
                  <span aria-hidden="true">{`${step.n} · ${label}`}</span>
                </button>
              ) : (
                <>
                  <span className="sr-only">{`Step ${step.n} of ${steps.length}, ${label}`}</span>
                  <span aria-hidden="true">{`${step.n} · ${label}`}</span>
                </>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
