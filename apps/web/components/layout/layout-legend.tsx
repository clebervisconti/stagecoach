import type { LayoutRole } from "@/lib/online";

const COPY: Record<LayoutRole, { name: string; body: string; style: string }> = {
  camera: {
    name: "Camera",
    body: "Your camera. Framing, light and where you look are measured only here.",
    style: "border-solid",
  },
  screen: {
    name: "Screen",
    body: "Your shared screen. Slide changes and demo flow are measured here.",
    style: "border-dashed",
  },
  ignore: {
    name: "Ignored",
    body: "Never analysed. Other people, chat panels and platform bars.",
    style: "border-dotted",
  },
  other_participant: {
    name: "Ignored",
    body: "Never analysed. Other people, chat panels and platform bars.",
    style: "border-dotted",
  },
};

export function LayoutLegend({ roles }: { roles: LayoutRole[] }) {
  if (!roles.length) return null;
  return (
    <div>
      <p className="cs-eyebrow">What the boxes mean</p>
      <ul className="mt-3 space-y-3">
        {roles.map((role) => {
          const item = COPY[role];
          const ignored = role === "ignore" || role === "other_participant";
          return (
            <li key={role} className="flex items-start gap-3">
              <span
                aria-hidden="true"
                className={`mt-1 h-[26px] w-10 shrink-0 border-2 border-current text-[color:var(--text-strong)] ${item.style}`}
                style={
                  ignored
                    ? {
                        background:
                          "repeating-linear-gradient(45deg, currentColor 0 1px, transparent 1px 6px)",
                      }
                    : undefined
                }
              />
              <span>
                <span className="block text-xs uppercase tracking-[0.08em]">{item.name}</span>
                <span className="mt-1 block text-sm text-[color:var(--text-secondary)]">{item.body}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
