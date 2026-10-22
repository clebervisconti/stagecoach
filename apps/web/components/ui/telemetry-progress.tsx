export function TelemetryProgress({
  value,
  label,
}: {
  value: number;
  label: string;
}) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-valuetext={label}
      className="relative mt-3 h-4"
    >
      <div
        className="absolute inset-x-0 top-0 h-1.5 bg-[color:var(--text-strong)] transition-[width] duration-200 ease-linear"
        style={{ width: `${pct}%` }}
      />
      <svg className="absolute inset-x-0 bottom-0 h-2 w-full text-[color:var(--line)]" viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true">
        {Array.from({ length: 13 }, (_, index) => {
          const x = index * (100 / 12);
          const major = index % 5 === 0;
          return (
            <line
              key={index}
              x1={x}
              x2={x}
              y1={major ? 0 : 3}
              y2={8}
              stroke="currentColor"
              strokeWidth="0.4"
            />
          );
        })}
      </svg>
    </div>
  );
}
