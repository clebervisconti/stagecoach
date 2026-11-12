"use client";

import { useEffect } from "react";
import { readPrivacySignals, rumInitOptions } from "@/lib/rum";

/**
 * Browser RUM. The package is bundled from npm. The committed token is empty.
 * Inject NEXT_PUBLIC_SPLUNK_RUM_TOKEN at image build time only after an
 * explicit deploy go. A missing token skips initialization and must not
 * break the page. Do Not Track and Global Privacy Control skip initialization.
 * Attributes are redacted before export. Session replay is not loaded.
 */
export function Rum() {
  useEffect(() => {
    const signals = readPrivacySignals();
    const options = rumInitOptions({
      token: process.env.NEXT_PUBLIC_SPLUNK_RUM_TOKEN,
      doNotTrack: signals.doNotTrack,
      globalPrivacyControl: signals.globalPrivacyControl,
    });
    if (!options) return;

    let cancelled = false;
    import("@splunk/otel-web")
      .then(({ default: SplunkRum }) => {
        if (cancelled) return;
        SplunkRum.init(options as Parameters<typeof SplunkRum.init>[0]);
      })
      .catch(() => {
        // Telemetry must not break the page.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
