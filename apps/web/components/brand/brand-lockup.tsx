export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex min-w-0 items-center gap-2 md:gap-4" data-testid="brand-lockup">
      <span
        className={compact ? "cs-brand-mark" : "cs-brand-lockup"}
        role="img"
        aria-label="CYBERSPHERE"
      />
      <span className="cs-product">Stage Coach</span>
    </div>
  );
}
