"use client";

import { useEffect } from "react";

/**
 * Browser RUM. The token is public by design and is injected at build time
 * from Keychain item cyberlabs-splunk-rum-token. A missing token disables
 * telemetry and must not break the page.
 */
export function Rum() {
  useEffect(() => {
    const token = process.env.NEXT_PUBLIC_SPLUNK_RUM_TOKEN;
    if (!token) return;

    let cancelled = false;
    import("@splunk/otel-web")
      .then(({ default: SplunkRum }) => {
        if (cancelled) return;
        SplunkRum.init({
          realm: "us1",
          rumAccessToken: token,
          applicationName: "stagecoach",
          deploymentEnvironment: "production",
        });
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
