import type { DeliveryMode } from "@/lib/online";

export function ModePictogram({ mode, className }: { mode: DeliveryMode; className?: string }) {
  const id = `pg-${mode}`;
  if (mode === "stage") {
    return (
      <svg
        className={className}
        viewBox="0 0 64 40"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="0.5" y="0.5" width="63" height="39" rx="2" strokeOpacity="0.5" />
        <rect x="7" y="6" width="28" height="16" strokeDasharray="2.5 2" />
        <path d="M5 33.5H59" strokeOpacity="0.5" />
        <g strokeOpacity="1">
          <circle cx="46" cy="19" r="2.99" />
          <path d="M40.25 28.43c0-3 2.2-4.6 5-4.6s5 1.6 5 4.6" />
        </g>
      </svg>
    );
  }
  if (mode === "webinar") {
    return (
      <svg
        className={className}
        viewBox="0 0 64 40"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <defs>
          <pattern id={id} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <path d="M0 0V3" stroke="currentColor" strokeWidth="0.6" strokeOpacity="0.6" />
          </pattern>
        </defs>
        <rect x="0.5" y="0.5" width="63" height="39" rx="2" strokeOpacity="0.5" />
        <rect x="5" y="5" width="37" height="30" strokeDasharray="2.5 2" />
        <rect x="45.5" y="5" width="13.5" height="9.5" />
        <g strokeOpacity="1">
          <circle cx="52.25" cy="8.3" r="1.43" />
          <path d="M49.50 12.81c0-3 2.2-4.6 5-4.6s5 1.6 5 4.6" />
        </g>
        <rect x="45.5" y="17.5" width="13.5" height="9.5" fill={`url(#${id})`} strokeDasharray="0.1 2" />
      </svg>
    );
  }
  if (mode === "online_talk") {
    return (
      <svg
        className={className}
        viewBox="0 0 64 40"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="0.5" y="0.5" width="63" height="39" rx="2" strokeOpacity="0.5" />
        <rect x="5" y="5" width="38" height="30" strokeDasharray="2.5 2" />
        <rect x="46" y="20" width="13" height="15" />
        <g strokeOpacity="1">
          <circle cx="52.5" cy="24.5" r="1.56" />
          <path d="M49.50 29.42c0-3 2.2-4.6 5-4.6s5 1.6 5 4.6" />
        </g>
      </svg>
    );
  }
  return (
    <svg
      className={className}
      viewBox="0 0 64 40"
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="0.5" y="0.5" width="63" height="39" rx="2" strokeOpacity="0.5" />
      <rect x="5" y="5" width="25" height="30" />
      <g strokeOpacity="1">
        <circle cx="17.5" cy="15" r="3.12" />
        <path d="M11.50 24.84c0-3 2.2-4.6 5-4.6s5 1.6 5 4.6" />
      </g>
      <rect x="34" y="5" width="25" height="30" strokeDasharray="2.5 2" />
      <path d="M32 9v22" strokeOpacity="0.5" strokeDasharray="0.1 2" />
    </svg>
  );
}
