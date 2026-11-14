export function BrandLockup() {
  return (
    <div className="flex items-center gap-3" data-testid="brand-lockup">
      <svg viewBox="0 0 32 32" width="32" height="32" aria-hidden="true" className="shrink-0 text-[color:var(--text-strong)]">
        <circle cx="16" cy="16" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="16" cy="16" r="1.5" fill="currentColor" />
      </svg>
      <span className="flex flex-col leading-none">
        <span className="cs-eyebrow">Cybersphere</span>
        <span className="cs-product">Stage Coach</span>
      </span>
    </div>
  );
}
