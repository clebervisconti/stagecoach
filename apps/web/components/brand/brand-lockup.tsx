/* Theme-swapped SVG marks. next/image does not swap these two files with the theme. */
/* eslint-disable @next/next/no-img-element */
export function BrandLockup() {
  return (
    <div className="s-brand" data-testid="brand-lockup">
      <span className="brand-swap" style={{ height: 32, width: 32 }} role="img" aria-label="CYBERSPHERE">
        <img className="brand-on-dark" src="/brand/mark-compact-on-dark.svg" alt="" width={32} height={32} />
        <img className="brand-on-light" src="/brand/mark-compact-on-light.svg" alt="" width={32} height={32} />
      </span>
      <span className="k-col" style={{ gap: 2 }}>
        <span className="brand-swap" style={{ height: 11 }} aria-hidden="true">
          <img className="brand-on-dark" src="/brand/wordmark-on-dark.svg" alt="" />
          <img className="brand-on-light" src="/brand/wordmark-on-light.svg" alt="" />
        </span>
        <span className="s-prod">Stage Coach</span>
      </span>
    </div>
  );
}

export function CompactMark({ size = 30 }: { size?: number }) {
  return (
    <span className="brand-swap" style={{ height: size, width: size }} aria-hidden="true">
      <img className="brand-on-dark" src="/brand/mark-compact-on-dark.svg" alt="" width={size} height={size} />
      <img className="brand-on-light" src="/brand/mark-compact-on-light.svg" alt="" width={size} height={size} />
    </span>
  );
}
